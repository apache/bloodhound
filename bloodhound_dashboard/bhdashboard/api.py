#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from inspect import isclass

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

The core of the dashboard architecture.
"""
__metaclass__ = type

from datetime import date, time, datetime, timedelta
from sys import version_info

from genshi.builder import tag

from trac.core import Component, ExtensionPoint, implements, \
        Interface, TracError
from trac.perm import IPermissionRequestor
from trac.resource import get_resource_url, Resource, resource_exists
from trac.util.compat import set
from trac.util.datefmt import parse_date
from trac.util.translation import _
from trac.web.chrome import add_stylesheet

#--------------------------------------
# Core classes and interfaces
#--------------------------------------

class IWidgetProvider(Interface):
    r"""Extension point interface for components providing widgets.
    These may be seen as web parts more sophisticated than WikiMacro 
    as they expose much more meta-data, but more simple than gadgets
    because they belong in the environment and are built on top of Trac
    architecture. This makes them more suitable to be used in 
    environments where flexibility and configurability is needed 
    (i.e. dashboards).
    """
    def get_widgets():
        """Return an iterable listing the names of the provided widgets."""

    def get_widget_description(name):
        """Return plain text description of the widget with specified name."""

    def get_widget_params(name):
        """Return a dictionary describing wigdet preference for the widget 
        with specified name. Used to customize widget behavior."""

    def render_widget(name, context, options):
        """Render widget considering given options."""

    # TODO: Add methods to specify widget metadata (e.g. parameters)

class ILayoutProvider(Interface):
    """Extension point interface implemented by components adding layouts
    to the dashboard.

    PS: Such components should implement `trac.mimeview.api.IContentConverter`
    interface so as to save and load layout definition when necessary.
    The pseudo-mimetype identifying layout data will be
    `application/x-trac-layout-<layout_name>`.
    Nonetheless they can delegate that task to other components too.
    Let's all hail the Trac component model !
    """
    def get_layouts():
        """Return an iterable listing the names of the provided layouts."""

    def get_layout_description(name):
        """Return plain text description of the layout with specified name."""

    def expand_layout(name, context, options):
        """Provide the information needed to render layout identified by
        `name`.
        
        :param context: rendering context
        :param options: additional options supplied in so as to adapt layout
                considering data specific to this request. This allows to 
                customize (parts of) the layout for a given request.
                Suported options are :

                :field schema:  data to be used in order to populate layout
                :field embed:   embed layout inside another page (true / false)
        """

class DashboardSystem(Component):
    implements(IPermissionRequestor, IWidgetProvider)

    widget_providers = ExtensionPoint(IWidgetProvider)
    layout_providers = ExtensionPoint(ILayoutProvider)

    # IPermissionRequestor methods
    def get_permission_actions(self):
        return ['DASHBOARD_VIEW',
                # 'DASHBOARD_CREATE', 'DASHBOARD_EDIT' <= Coming soon ;)
               ]

    # IWidgetProvider methods

    def get_widgets(self):
        """List the name of the widgets that will always be available
        """
        yield 'WidgetDoc'

    def get_widget_description(self, name):
        """Return plain text description of the widget with specified name.
        """
        try:
            return {
                    'WidgetDoc' : """Display widget documentation"""
                    }[name]
        except KeyError:
            raise InvalidIdentifier('Widget name MUST match any of ' +
                        ', '.join(self.get_widgets()),
                    title='Invalid widget identifier')

    def get_widget_params(self, name):
        """Return a dictionary describing wigdet preference for the widget 
        with specified name. Used to customize widget behavior.
        """
        try:
            return {
                    'WidgetDoc': {
                        'urn': {
                                'desc': """Widget name. If missing then """
                                        """documentation for all widgets """
                                        """will be displayed."""
                                }
                        }
                   }[name]
        except KeyError:
            raise InvalidIdentifier('Widget name MUST match any of ' +
                        ', '.join(self.get_widgets()),
                    title='Invalid widget identifier')

    def render_widget(self, name, context, options):
        """Render widget considering given options.
        """
        if name == 'WidgetDoc':
            add_stylesheet(context.req, 'dashboard/css/docs.css')
            widget_name, = self.bind_params(options,
                    self.get_widget_params(name), 'urn')
            if widget_name is not None:
                try:
                    providers = [([widget_name],
                            self.resolve_widget(widget_name))]
                except LookupError:
                    return 'widget_alert.html', {
                            'title': _('Widget documentation'),
                            'data': {
                                    'msglabel': 'Alert',
                                    'msgbody': 'Unknown identifier',
                                    'msgdetails': [
                                            ('Widget name', widget_name)
                                        ]
                                  }
                        }, context
            else:
                providers = [(provider.get_widgets(), provider) \
                        for provider in self.widget_providers]
            metadata = [self._prepare_doc_metadata(self.widget_metadata(wnm, p)) \
                    for widgets, p in providers for wnm in widgets]
            docs_resource = Resource('wiki', 'BloodhoundWidgets')
            insert_docs = resource_exists(self.env, docs_resource) and \
                    not (context.resource and \
                    docs_resource == context.resource)
            return 'widget_doc.html', {
                        'title': _('Widget documentation'),
                        'data': {
                                'items': metadata
                            },
                        'ctxtnav': [tag.a(tag.i(class_='icon-info-sign'),
                                    ' ', _('Help'),
                                    href=get_resource_url(
                                            self.env, docs_resource,
                                            context.href)
                                )] if insert_docs else [],
                    }, context
        else:
            raise InvalidIdentifier('Widget name MUST match any of ' +
                        ', '.join(self.get_widgets()),
                    title='Invalid widget identifier')

    # Public API
    def widget_metadata(self, nm, provider=None):
        """Retrieve widget metadata.

        :param nm:        Wid
        get name
        :param provider:  Widget provider. If omitted it will be resolved.
        """
        if provider is None:
            provider = self.resolve_widget(nm)
        return {
                'urn': nm,
                'desc': provider.get_widget_description(nm),
                'params': provider.get_widget_params(nm),
            }

    def _prepare_doc_metadata(self, spec):
        """Transform widget metadata into a format suitable to render
        documentation.
        """
        def plabel(p):
            v = p.get('type', str)
            module = getattr(v, '__module__', None)
            if module in (None, '__builtin__'):
                return getattr(v, '__name__', None) or v
            else:
                # FIXME: Improve e.g. for enum fields
                if not isclass(v):
                    v = v.__class__
                return tag.span(v.__name__, title='in ' + module)

        return {
                'title': spec['urn'],
                'desc': '\n'.join(l.strip()
                                   for l in spec['desc'].splitlines()),
                'sections': [
                        {
                            'title': _('Parameters'),
                            'entries': [
                                    {
                                        'caption': pnm,
                                        'summary': '\n'.join(
                                                l.strip() for l in \
                                                p.get('desc').splitlines()),
                                        'details': [
                                                ('Type', plabel(p)),
                                                ('Required', p.get('required',
                                                                   False)),
                                                ('Default', p.get('default')),
                                            ]
                                    }
                                for pnm, p in spec['params'].iteritems()]
                        }
                    ]
            }


    def bind_params(self, options, spec, *params):
        """Extract values for widget arguments from `options` and ensure 
        they are valid and properly formatted.
        """
        # Should this helper function be part of public API ?
        def get_and_check(p):
            try:
                param_spec = spec[p]
            except KeyError:
                raise InvalidWidgetArgument("Unknown parameter `%s`" % (p,))
            try:
                argtype = param_spec.get('type') or unicode
                return argtype(options['args'][p])
            except KeyError:
                if param_spec.get('required'):
                    raise InvalidWidgetArgument(p,
                            "Required parameter expected")
                elif param_spec.get('default') is not None:
                    return param_spec['default']
                else:
                    return None
        return (get_and_check(param) for param in params)

    def _resolve(self, objnm, epnm, accessor, errmsg='Invalid object name %s'):
        """Determine the provider implementing a given widget / layout / ...

        :param objnm:     name used to lookup provider
        :param epnm:      attribute name used for entry point
        :param accessor:  function used to determine names bound to provider
        """
        for p in getattr(self, epnm):
            if objnm in accessor(self, p):
                return p
        else:
            raise LookupError(errmsg % (objnm,))

    def resolve_layout(self, nm):
        return self._resolve(nm, 'layout_providers', 
                lambda _, lp: lp.get_layouts() , "No provider for layout %s")

    def resolve_widget(self, nm):
        return self._resolve(nm, 'widget_providers', 
                lambda _, wp: wp.get_widgets() , "No provider for widget %s")

#--------------------------------------
# Exception classes
#--------------------------------------

# Maybe it is better to move these to a separate file 
# (if this gets as big as it seems it will be)

class WidgetException(TracError):
    """Base class for all errors related to Trac widgets"""

class InvalidIdentifier(WidgetException):
    """Invalid value for a field used to identify an internal object"""

    title = 'Invalid identifier'

class InvalidWidgetArgument(WidgetException):
    """Something went wrong with widget parameter"""

    title = 'Invalid Argument'

    def __init__(self, argname, message, title=None, show_traceback=False):
        message = _("Invalid argument `") + argname + "`. " + message
        TracError.__init__(self, message, title, show_traceback)
        self.argname = argname

    def __unicode__(self):
        return unicode(
                self.message)

#--------------------------------------
# Default field types
#--------------------------------------

class DateField:
    """Convert datetime field
    """
    def __init__(self, fmt="%Y-%m-%d %H:%M:%S", tz=None):
        """Initialize datetime field converter

        :param fmt:       format string used to interpret dates and times
        """
        self.fmt = fmt
        self.tz = tz

    def __call__(self, value, fmt=None):
        """Perform the actual conversion
        """
        if isinstance(value, (date, time, datetime, timedelta)):
            return value
        elif isinstance(value, basestring):
            try:
                return parse_date(value, self.tz)
            except TracError, exc:
                try:
                    fmt = fmt or self.fmt
                    return datetime.strptime(value, fmt)
                except:
                    raise InvalidWidgetArgument(
                            error=exc, title=_('Datetime conversion error'))
        elif isinstance(value, int):
            return datetime.utcfromtimestamp(value)
        else:
            raise InvalidWidgetArgument(
                    "Invalid format `%s` for value `%s`" % (fmt, value),
                    title=_('Datetime conversion error'))

class ListField:
    """Convert list field
    """
    def __init__(self, sep=','):
        """Initialize list field converter

        :param sep:       character used to delimit list items
        """
        self.sep = sep

    def __call__(self, value):
        """Perform the actual conversion
        """
        if isinstance(value, basestring):
            return value.split(self.sep)
        else:
            try:
                return list(value)
            except Exception, exc:
                raise InvalidWidgetArgument(error=exc, 
                        title=_('List conversion error'))

class EnumField:
    """Convert enum field
    """
    def __init__(self, *choices):
        """Initialize enum field converter

        :param choices:       allowed values
        """
        self.choices = set(choices)

    def __call__(self, value):
        """Perform the actual conversion
        """
        if value not in self.choices:
            raise InvalidWidgetArgument('',
                _('Expected one of `%s` but got `%s`') % (self.choices, value),
                title=_('Enum conversion error'))
        return value

class JsonField:
    """Deserialize JSON string
    """
    def __init__(self):
        """Initialize JSON field converter
        """
        # TODO: Add further options

    def __call__(self, value):
        """Perform the actual conversion
        """
        try:
            if version_info < (2, 6):
                from simplejson import loads
            else:
                from json import loads
        except ImportError:
            raise TracError('Unable to load library to parse JSON string')
        else:
            return loads(value)

