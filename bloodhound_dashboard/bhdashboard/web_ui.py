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

Implementing dashboard user interface.
"""

__metaclass__ = type

import copy
import pkg_resources
import re
from uuid import uuid4

from genshi.builder import tag
from genshi.core import Stream
from trac.core import Component, implements
from trac.config import Option, IntOption
from trac.mimeview.api import Context
from trac.util.translation import _
from trac.ticket.query import QueryModule
from trac.ticket.report import ReportModule
from trac.util.compat import groupby
from trac.util.translation import _
from trac.web.api import IRequestHandler, IRequestFilter
from trac.web.chrome import add_ctxtnav, add_stylesheet, Chrome, \
                            INavigationContributor, ITemplateProvider

from bhdashboard.api import DashboardSystem, InvalidIdentifier
from bhdashboard import _json
from multiproduct.env import ProductEnvironment


class DashboardModule(Component):
    """Web frontend for dashboard infrastructure.
    """
    implements(IRequestHandler, IRequestFilter, INavigationContributor,
               ITemplateProvider)

    mainnav_label = Option('mainnav', 'tickets.label', 'Tickets',
                           """Dashboard label in mainnav""")
    default_widget_height = IntOption('widgets', 'default_height', 320,
                                      """Default widget height in pixels""")

    # IRequestFilter methods

    def pre_process_request(self, req, handler):
        """Always returns the request handler unchanged.
        """
        return handler

    def post_process_request(self, req, template, data, content_type):
        """Inject dashboard helpers in data.
        """
        if data is not None:
            data['bhdb'] = DashboardChrome(self.env)
            if isinstance(req.perm.env, ProductEnvironment) \
                    and not 'resourcepath_template' in data \
                    and 'product_list' in data:
                data['resourcepath_template'] = 'bh_path_general.html'
        for item in req.chrome['nav'].get('mainnav', []):
            self.log.debug('%s' % (item,))
            if item['name'] == 'tickets':
                item['label'] = tag.a(_(self.mainnav_label),
                                      href=req.href.dashboard())
                if item['active'] and \
                        not ReportModule(self.env).match_request(req):
                    add_ctxtnav(req, _('Reports'),
                                href=req.href.report())
                break
        return template, data, content_type

    # IRequestHandler methods
    def match_request(self, req):
        """Match dashboard prefix"""
        return bool(re.match(r'^/dashboard(/.)?', req.path_info))

    def process_request(self, req):
        req.perm.require('PRODUCT_VIEW')
        # Initially this will render static widgets. With time it will be
        # more and more dynamic and flexible.
        if self.env[QueryModule] is not None:
            add_ctxtnav(req, _('Custom Query'), req.href.query())
        if self.env[ReportModule] is not None:
            add_ctxtnav(req, _('Reports'), req.href.report())
        context = Context.from_request(req)
        template, layout_data = self.expand_layout_data(context,
            'bootstrap_grid',
            self.DASHBOARD_SCHEMA if isinstance(self.env, ProductEnvironment)
            else self.DASHBOARD_GLOBAL_SCHEMA
        )
        widgets = self.expand_widget_data(context, layout_data) 
        return template, {
            'context': Context.from_request(req),
            'layout': layout_data,
            'widgets': widgets,
            'title': _(self.mainnav_label),
            'default': {'height': self.default_widget_height or None}
        }, None

    # INavigationContributor methods
    def get_active_navigation_item(self, req):
        """Highlight dashboard mainnav item.
        """
        return 'tickets'

    def get_navigation_items(self, req):
        """Skip silently
        """
        return None

    # ITemplateProvider methods
    def get_htdocs_dirs(self):
        """List `htdocs` dirs for dashboard and widgets.
        """
        resource_filename = pkg_resources.resource_filename
        return [('dashboard', resource_filename('bhdashboard', 'htdocs')),
                #('widgets', resource_filename('bhdashboard.widgets', 'htdocs'))
                ('layouts', resource_filename('bhdashboard.layouts', 'htdocs'))]

    def get_templates_dirs(self):
        """List `templates` folders for dashboard and widgets.
        """
        resource_filename = pkg_resources.resource_filename
        return [resource_filename('bhdashboard.layouts', 'templates'),
                resource_filename('bhdashboard', 'templates'),
                resource_filename('bhdashboard.widgets', 'templates')]

    # Temp vars
    DASHBOARD_SCHEMA = {
            'div': [
                    {
                        '_class': 'row',
                        'div': [
                                {
                                    '_class': 'span8',
                                    'widgets': ['my tickets', 'active tickets',
                                                'products', 'versions',
                                                'milestones', 'components']
                                },
                                {
                                    '_class': 'span4',
                                    'widgets': ['activity']
                                }
                            ]
                    }
                ],
            'widgets': {
                    'components': {
                            'args': [
                                'TicketFieldValues',
                                None,
                                {'args': {
                                    'field': 'component',
                                    'title': 'Components',
                                    'verbose': True}}]
                        },
                    'milestones': {
                            'args': [
                                'TicketFieldValues',
                                None,
                                {'args': {
                                    'field': 'milestone',
                                    'title': 'Milestones',
                                    'verbose': True}}]
                        },
                    'versions': {
                            'args': [
                                'TicketFieldValues',
                                None,
                                {'args' : {
                                    'field' : 'version',
                                    'title' : 'Versions',
                                    'verbose' : True}}]
                        },
                    'active tickets': {
                            'args': [
                                'TicketQuery',
                                None,
                                {'args': {
                                    'max' : 10,
                                    'query': 'status=!closed&group=milestone'
                                        '&col=id&col=summary&col=owner'
                                        '&col=status&col=priority&'
                                        'order=priority',
                                    'title': 'Active Tickets'}}],
                            'altlinks': False
                        },
                    'my tickets': {
                            'args': [
                                'TicketQuery',
                                None,
                                {'args': {
                                 'max': 10,
                                 'query': 'status=!closed&group=milestone'
                                          '&col=id&col=summary&col=owner'
                                          '&col=status&col=priority&'
                                          'order=priority&'
                                          'owner=$USER',
                                    'title': 'My Tickets'}
                                }],
                            'altlinks': False
                        },
                    'activity': {
                            'args': ['Timeline', None, {'args': {}}]
                        },
                    'products': {
                            'args': ['Product', None, {'args': {'max': 3, 
                                                                'cols': 2}}]
                        },
               }
        }

    # global dashboard queries: add milestone column, group by product
    DASHBOARD_GLOBAL_SCHEMA = copy.deepcopy(DASHBOARD_SCHEMA)
    DASHBOARD_GLOBAL_SCHEMA['widgets']['active tickets']['args'][2]['args']['query'] = (
        'status=!closed&group=product&col=id&col=summary&col=owner&col=status&'
        'col=priority&order=priority&col=milestone'
    )
    DASHBOARD_GLOBAL_SCHEMA['widgets']['my tickets']['args'][2]['args']['query'] = (
        'status=!closed&group=product&col=id&col=summary&col=owner&col=status&'
        'col=priority&order=priority&col=milestone&owner=$USER&'
    )
    for widget in ('milestones', 'versions', 'components'):
        DASHBOARD_GLOBAL_SCHEMA['div'][0]['div'][0]['widgets'].remove(widget)

    # Public API
    def expand_layout_data(self, context, layout_name, schema, embed=False):
        """Determine the template needed to render a specific layout
        and the data needed to place the widgets at expected
        location.
        """
        layout = DashboardSystem(self.env).resolve_layout(layout_name)

        template = layout.expand_layout(layout_name, context, {
            'schema': schema,
            'embed': embed
        })['template']
        return template, schema

    def _render_widget(self, wp, name, ctx, options):
        """Render widget without failing.
        """
        if wp is None:
            data = {'msglabel': 'Warning',
                    'msgbody': _('Unknown widget %(name)s', name=name)}
            return 'widget_alert.html', {'title': '', 'data': data}, ctx

        try:
            return wp.render_widget(name, ctx, options)
        except Exception, exc:
            log_entry = str(uuid4())
            exccls = exc.__class__
            self.log.exception(
                "- %s - Error rendering widget %s with options %s",
                log_entry, name, options)
            data = {
                'msgtype': 'error',
                'msglabel': 'Error',
                'msgbody': _('Exception raised while rendering widget. '
                             'Contact your administrator for further details.'),
                'msgdetails': [
                    ('Widget name', name),
                    ('Exception type', tag.code(exccls.__name__)),
                    ('Log entry ID', log_entry),
                ],
            }
            return 'widget_alert.html', {
                'title': _('Widget error'),
                'data': data
            }, ctx

    def expand_widget_data(self, context, schema):
        """Expand raw widget data and format it for use in template
        """
        # TODO: Implement dynamic dashboard specification
        widgets_spec = schema.get('widgets', {})
        widgets_index = dict([wnm, wp]
            for wp in DashboardSystem(self.env).widget_providers
            for wnm in wp.get_widgets()
        )
        self.log.debug("Bloodhound: Widget index %s" % (widgets_index,))
        for w in widgets_spec.itervalues():
            w['c'] = widgets_index.get(w['args'][0])
            w['args'][1] = context
        self.log.debug("Bloodhound: Widget specs %s" % (widgets_spec,))
        chrome = Chrome(self.env)
        render = chrome.render_template
        data_strm = ((k, w, self._render_widget(w['c'], *w['args']))
                     for k, w in widgets_spec.iteritems())
        return dict([k, {'title': data['title'],
                         'content': render(wctx.req, template, data['data'],
                                           fragment=True),
                         'ctxtnav': w.get('ctxtnav', True) and
                                    data.get('ctxtnav') or None,
                         'altlinks': w.get('altlinks', True) and
                                     data.get('altlinks') or None,
                         'visible': w['c'] is not None or
                                    not w.get('hide_disabled', False)}
                     ] for k, w, (template, data, wctx) in data_strm)

    def alert_disabled(self):
        return tag.div(tag.span('Error', class_='label label-important'),
                       ' Could not load dashboard. Is ', 
                       tag.code('bhdashboard.web_ui.DashboardModule'), 
                       ' component disabled ?',
                       class_='alert alert-error')

#------------------------------------------------------
#    Dashboard Helpers to be used in templates
#------------------------------------------------------

XMLNS_DASHBOARD_UI = 'http://issues.apache.org/bloodhound/wiki/Ui/Dashboard'


class DashboardChrome:
    """Helper functions providing access to dashboard infrastructure 
    in Genshi templates. Useful to reuse layouts and widgets across
    website.
    """
    def __init__(self, env):
        self.env = env

    def embed_layout(self, context, layout, **kwargs):
        """Render layout and widgets

        :param context: Rendering context
        :param layout: Identifier of target layout
        :param schema: Data describing widget positioning
        :param widgets: Widgets definition
        """
        dbmod = DashboardModule(self.env)
        schema = kwargs.get('schema', {})
        if isinstance(schema, basestring):
            schema = _json.loads(schema)
        widgets = kwargs.get('widgets')
        if widgets is not None:
            # TODO: Use this one once widgets markup parser will be ready
            #widgets = parse_widgets_markup(widgets)
            if isinstance(widgets, basestring):
                widgets = _json.loads(widgets)
        else:
            widgets = {}
        schema['widgets'] = widgets
        template, layout_data = dbmod.expand_layout_data(context, layout,
                                                         schema, True)
        widgets = dbmod.expand_widget_data(context, layout_data)
        return Chrome(self.env).render_template(
            context.req, template,
            dict(context=context, layout=layout_data, widgets=widgets, title='',
                 default={'height': dbmod.default_widget_height or None}),
            fragment=True)

    def expand_widget(self, context, widget):
        """Render single widget

        :param context: Rendering context
        :param widget: Widget definition
        """
        dbmod = DashboardModule(self.env)
        options = widget['args'][2]
        argsdef = options.get('args')
        if isinstance(argsdef, basestring):
            options['args'] = _json.loads(argsdef)
        elif isinstance(argsdef, Stream):
            options['args'] = parse_args_tag(argsdef)
        return dbmod.expand_widget_data(context, {'widgets': {0: widget}})[0]

#------------------------------------------------------
#    Stream processors
#------------------------------------------------------


def parse_args_tag(stream):
    """Parse Genshi Markup for widget arguments
    """
    args = {}
    inside = False
    argnm = ''
    argvalue = ''
    for kind, data, _ in stream:
        if kind == Stream.START:
            qname, attrs = data
            if qname.namespace == XMLNS_DASHBOARD_UI \
                    and qname.localname == 'arg':
                if inside:
                    raise RuntimeError('Nested bh:arg tag')
                else:
                    argnm = attrs.get('name')
                    argvalue = ''
                    inside = True
        elif kind == Stream.TEXT:
            argvalue += data
        elif kind == Stream.END:
            if qname.namespace == XMLNS_DASHBOARD_UI \
                    and qname.localname == 'arg':
                args[argnm] = argvalue
                inside = False
    return args
