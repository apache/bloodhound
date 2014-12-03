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

Widget helpers functions and classes.
"""
import inspect

from trac.core import Component, implements
from trac.util.text import to_unicode

from bhdashboard.api import DashboardSystem, IWidgetProvider, InvalidIdentifier

#------------------------------------------------------
#    Widget helpers
#------------------------------------------------------

class WidgetBase(Component):
    """Abstract base class for widgets"""

    implements(IWidgetProvider)
    abstract = True

    def get_widgets(self):
        """Yield the name of the widget based on the class name."""
        name = self.__class__.__name__
        if name.endswith('Widget'):
            name = name[:-6]
        yield name

    def get_widget_description(self, name):
        """Return the subclass's docstring."""
        return to_unicode(inspect.getdoc(self.__class__))

    def get_widget_params(self, name):
        """Return a dictionary containing arguments specification for
        the widget with specified name.
        """
        raise NotImplementedError

    def render_widget(self, context, name, options):
        """Render widget considering given options."""
        raise NotImplementedError

    # Helper methods
    def bind_params(self, name, options, *params):
        return DashboardSystem(self.env).bind_params(options, 
                self.get_widget_params(name), *params)

def check_widget_name(f):
    """Decorator used to wrap methods of widget providers so as to ensure
    widget names will match those listed by `get_widgets` method.
    """
    def widget_name_checker(self, name, *args, **kwargs):
        names = set(self.get_widgets())
        if name not in names: 
            raise InvalidIdentifier('Widget name MUST match any of ' + 
                        ', '.join(names), 
                    title='Invalid widget identifier')
        return f(self, name, *args, **kwargs)
    return widget_name_checker
