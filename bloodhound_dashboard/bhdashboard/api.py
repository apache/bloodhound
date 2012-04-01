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

The core of the dashboard architecture.
"""
__metaclass__ = type

from datetime import date, time, datetime, timedelta

from trac.core import Component, ExtensionPoint, implements, \
        Interface, TracError
from trac.perm import IPermissionRequestor
from trac.util.compat import set
from trac.util.datefmt import parse_date
from trac.util.translation import _

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
        """

class DashboardSystem(Component):
    implements(IPermissionRequestor)

    providers = ExtensionPoint(IWidgetProvider)

    # IPermissionRequestor methods
    def get_permission_actions(self):
        return ['DASHBOARD_VIEW',
                # 'DASHBOARD_CREATE', 'DASHBOARD_EDIT' <= Coming soon ;)
               ]

    # Public API
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
                elif param_spec.get('default') is not None :
                    return param_spec['default']
                else:
                    return None
        return (get_and_check(param) for param in params)

#--------------------------------------
# Exfeption classes
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
        TracError.__init__(self, message, title, show_traceback)
        self.argname = argname
    
    def __unicode__(self):
        return unicode(_("Invalid argument `") + self.argname + "`. " + \
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
            raise InvalidWidgetArgument(
                _('Expected one of `%s` but got `%s`') % (self.choices, value),
                title=_('Enum conversion error'))
        return value

