#!/usr/bin/env python
# -*- coding: UTF-8 -*-

#  Licensed to the Apache Software Foundation (ASF) under one
#  or more contributor license agreements.  See the NOTICE file
#  distributed with this work for additional information
#  regarding copyright ownership.  The ASF licenses this file
#  to you under the Apache License, Version 2.0 (the
#  "License"); you may not use this file except in compliance
#  with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing,
#  software distributed under the License is distributed on an
#  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#  KIND, either express or implied.  See the License for the
#  specific language governing permissions and limitations
#  under the License.


r"""Project dashboard for Apache(TM) Bloodhound

Widgets displaying timeline data.
"""

from datetime import datetime, date, time, timedelta
from itertools import imap, islice
from types import MethodType

from genshi.builder import tag
from trac.core import Component, ExtensionPoint, implements, Interface, \
        TracError
from trac.config import IntOption
from trac.mimeview.api import RenderingContext
from trac.resource import Resource, resource_exists, ResourceNotFound
from trac.timeline.web_ui import TimelineModule
from trac.ticket.api import TicketSystem
from trac.ticket.model import Ticket
from trac.ticket.web_ui import TicketModule
from trac.util.datefmt import utc
from trac.util.translation import _, tag_
from trac.web.chrome import add_stylesheet

from bhdashboard.api import DateField, EnumField, ListField
from bhdashboard.util import WidgetBase, InvalidIdentifier, \
                              check_widget_name, dummy_request, \
                              merge_links, pretty_wrapper, trac_version, \
                              trac_tags

__metaclass__ = type


class ITimelineEventsFilter(Interface):
    """Filter timeline events displayed in a rendering context
    """
    def supported_providers():
        """List supported timeline providers. Filtering process will take 
        place only for the events contributed by listed providers.
        Return `None` and all events contributed by all timeline providers 
        will be processed.
        """
    def filter_event(context, provider, event, filters):
        """Decide whether a timeline event is relevant in a rendering context.

        :param context: rendering context, used to determine events scope
        :param provider: provider contributing event
        :param event: target event
        :param filters: active timeline filters
        :return: the event resulting from the filtering process or 
                  `None` if it has to be removed from the event stream or
                  `NotImplemented` if the filter doesn't care about it.
        """


class TimelineWidget(WidgetBase):
    """Display activity feed.
    """
    default_count = IntOption('widget_activity', 'limit', 25, 
        """Maximum number of items displayed by default""")

    event_filters = ExtensionPoint(ITimelineEventsFilter)

    _filters_map = None

    @property
    def filters_map(self):
        """Quick access to timeline events filters to be applied for a 
        given timeline provider.
        """
        if self._filters_map is None:
            self._filters_map = {}
            for _filter in self.event_filters:
                providers = _filter.supported_providers()
                if providers is None:
                    providers = [None]
                for p in providers:
                    self._filters_map.setdefault(p, []).append(_filter)
        return self._filters_map

    def get_widget_params(self, name):
        """Return a dictionary containing arguments specification for
        the widget with specified name.
        """
        return {
            'from': {
                'desc': """Display events before this date""",
                'type': DateField(),  # TODO: Custom datetime format
            },
            'daysback': {
                'desc': """Event time window""",
                'type': int,
            },
            'precision': {
                'desc': """Time precision""",
                'type': EnumField('second', 'minute', 'hour')
            },
            'doneby': {
                'desc': """Filter events related to user""",
            },
            'filters': {
                'desc': """Event filters""",
                'type': ListField()
            },
            'max': {
                'desc': """Limit the number of events displayed""",
                'type': int
            },
            'realm': {
                'desc': """Resource realm. Used to filter events""",
            },
            'id': {
                'desc': """Resource ID. Used to filter events""",
            },
        }
    get_widget_params = pretty_wrapper(get_widget_params, check_widget_name)

    def render_widget(self, name, context, options):
        """Gather timeline events and render data in compact view
        """
        data = None
        req = context.req
        try:
            timemdl = self.env[TimelineModule]
            admin_page = tag.a(_("administration page."),
                               title=_("Plugin Administration Page"),
                               href=req.href.admin('general/plugin'))
            if timemdl is None:
                return 'widget_alert.html', {
                    'title':  _("Activity"),
                    'data': {
                        'msglabel': "Warning",
                        'msgbody':
                            tag_("The TimelineWidget is disabled because the "
                                 "Timeline component is not available. "
                                  "Is the component disabled? "
                                  "You can enable from the %(page)s",
                                  page=admin_page),
                        'dismiss': False,
                    }
                }, context

            params = ('from', 'daysback', 'doneby', 'precision', 'filters',
                      'max', 'realm', 'id')
            start, days, user, precision, filters, count, realm, rid = \
                self.bind_params(name, options, *params)
            if context.resource.realm == 'ticket':
                if days is None:
                    # calculate a long enough time daysback
                    ticket = Ticket(self.env, context.resource.id)
                    ticket_age = datetime.now(utc) - ticket.time_created
                    days = ticket_age.days + 1
                if count is None:
                    # ignore short count for ticket feeds
                    count = 0
            if count is None:
                count = self.default_count

            fakereq = dummy_request(self.env, req.authname)
            fakereq.args = {
                'author': user or '',
                'daysback': days or '',
                'max': count,
                'precision': precision,
                'user': user
            }
            if filters:
                fakereq.args.update(dict((k, True) for k in filters))
            if start is not None:
                fakereq.args['from'] = start.strftime('%x %X')

            wcontext = context.child()
            if (realm, rid) != (None, None):
                # Override rendering context
                resource = Resource(realm, rid)
                if resource_exists(self.env, resource) or \
                        realm == rid == '':
                    wcontext = context.child(resource)
                    wcontext.req = req
                else:
                    self.log.warning("TimelineWidget: Resource %s not found",
                                     resource)
            # FIXME: Filter also if existence check is not conclusive ?
            if resource_exists(self.env, wcontext.resource):
                module = FilteredTimeline(self.env, wcontext)
                self.log.debug('Filtering timeline events for %s',
                               wcontext.resource)
            else:
                module = timemdl
            data = module.process_request(fakereq)[1]
        except TracError, exc:
            if data is not None:
                exc.title = data.get('title', 'Activity')
            raise
        else:
            merge_links(srcreq=fakereq, dstreq=req,
                        exclude=["stylesheet", "alternate"])
            if 'context' in data:
                # Needed for abbreviated messages in widget events (#340)
                wcontext.set_hints(**(data['context']._hints or {}))
            data['context'] = wcontext
            return 'widget_timeline.html', {
                'title': _('Activity'),
                'data': data,
                'altlinks': fakereq.chrome.get('links', {}).get('alternate')
            }, context

    render_widget = pretty_wrapper(render_widget, check_widget_name)


class FilteredTimeline:
    """This is a class (not a component ;) aimed at overriding some parts of
    TimelineModule without patching it in order to inject code needed to filter
    timeline events according to rendering context. It acts as a wrapper on top
    of TimelineModule.
    """
    def __init__(self, env, context, keep_mismatched=False):
        """Initialization

        :param env: Environment object
        :param context: Rendering context
        """
        self.env = env
        self.context = context
        self.keep_mismatched = keep_mismatched

    # Access to TimelineModule's members

    process_request = TimelineModule.__dict__['process_request']
    _provider_failure = TimelineModule.__dict__['_provider_failure']
    _event_data = TimelineModule.__dict__['_event_data']
    _max_daysback = TimelineModule.max_daysback

    @property
    def max_daysback(self):
        return (-1 if self.context.resource.realm == 'ticket'
                else self._max_daysback)

    @property
    def event_providers(self):
        """Introduce wrappers around timeline event providers in order to
        filter event streams.
        """
        for p in TimelineModule(self.env).event_providers:
            yield TimelineFilterAdapter(p, self.context, self.keep_mismatched)

    def __getattr__(self, attrnm):
        """Forward attribute access request to TimelineModule
        """
        try:
            value = getattr(TimelineModule(self.env), attrnm)
            if isinstance(value, MethodType):
                raise AttributeError()
        except AttributeError:
            raise AttributeError("'%s' object has no attribute '%s'"
                                 % (self.__class__.__name__, attrnm))
        else:
            return value


class TimelineFilterAdapter:
    """Wrapper class used to filter timeline event streams transparently.
    Therefore it is compatible with `ITimelineEventProvider` interface 
    and reuses the implementation provided by real provider.
    """
    def __init__(self, provider, context, keep_mismatched=False):
        """Initialize wrapper object by providing real timeline events provider.
        """
        self.provider = provider
        self.context = context
        self.keep_mismatched = keep_mismatched

    # ITimelineEventProvider methods

    def get_timeline_filters(self, req):
        gen = self.provider.get_timeline_filters(req)
        if self.context.resource.realm == 'ticket' and \
                isinstance(self.provider, TicketModule) and \
                'TICKET_VIEW' in req.perm:
            # ensure ticket_details appears once if this is a query on a ticket
            gen = list(gen)
            if not [g for g in gen if g[0] == 'ticket_details']:
                gen.append(('ticket_details', _("Ticket updates"), False))
        return gen
    
    #def render_timeline_event(self, context, field, event):

    def get_timeline_events(self, req, start, stop, filters):
        """Filter timeline events according to context.
        """
        filters_map = TimelineWidget(self.env).filters_map
        evfilters = filters_map.get(self.provider.__class__.__name__, []) + \
            filters_map.get(None, [])
        self.log.debug('Applying filters %s for %s against %s', evfilters, 
                       self.context.resource, self.provider)
        if evfilters:
            for event in self.provider.get_timeline_events(
                    req, start, stop, filters):
                match = False
                for f in evfilters:
                    new_event = f.filter_event(self.context, self.provider,
                                               event, filters)
                    if new_event is None:
                        event = None
                        match = True
                        break
                    elif new_event is NotImplemented:
                        pass
                    else:
                        event = new_event
                        match = True
                if event is not None and (match or self.keep_mismatched):
                    yield event
        else:
            if self.keep_mismatched:
                for event in self.provider.get_timeline_events(
                        req, start, stop, filters):
                    yield event

    def __getattr__(self, attrnm):
        """Forward attribute access request to real provider
        """
        try:
            value = getattr(self.provider, attrnm)
        except AttributeError:
            raise AttributeError("'%s' object has no attribute '%s'"
                                 % (self.__class__.__name__, attrnm))
        else:
            return value


class TicketFieldTimelineFilter(Component):
    """A class filtering ticket events related to a given resource
    associated via ticket fields.
    """
    implements(ITimelineEventsFilter)

    @property
    def fields(self):
        """Available ticket fields
        """
        field_names = getattr(self, '_fields', None)
        if field_names is None:
            self._fields = set(f['name'] for f in
                               TicketSystem(self.env).get_ticket_fields())
        return self._fields

    # ITimelineEventsFilter methods

    def supported_providers(self):
        """This filter will work on ticket events. It also intercepts events
        even when multi-product ticket module is installed.
        """
        yield 'TicketModule'
        yield 'ProductTicketModule'

    def filter_event(self, context, provider, event, filters):
        """Decide whether the target of a ticket event has a particular custom
        field set to the context resource's identifier.
        """
        if context.resource is not None:
            field_name = context.resource.realm
            if field_name in self.fields.union(['ticket']):
                try:
                    ticket_ids = event[3][0]
                except:
                    self.log.exception('Unknown ticket event %s ... [SKIP]',
                                       event)
                    return None

                if not isinstance(ticket_ids, list):
                    ticket_ids = [ticket_ids]
                context._ticket_cache = ticket_cache = \
                    getattr(context, '_ticket_cache', None) or {}
                for t in ticket_ids:
                    if isinstance(t, Resource):
                        if event[0] != 'attachment':
                            t = t.id
                        else:
                            t = t.parent.id
                    try:
                        t = ticket_cache.get(t) or Ticket(self.env, t)
                    except ResourceNotFound:
                        return None
                    if field_name == 'ticket' and t.id == context.resource.id:
                        return event
                    if t[field_name] == context.resource.id:
                        return event
                    ticket_cache[t.id] = t
                else:
                    return None
        return NotImplemented
