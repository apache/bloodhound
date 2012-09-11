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

Widgets acting as containers.
"""

from genshi.builder import tag
from trac.core import implements, TracError

from bhdashboard.api import DashboardSystem, InvalidWidgetArgument, JsonField
from bhdashboard.util import WidgetBase, check_widget_name, \
                              dummy_request, merge_links, minmax, \
                              pretty_wrapper, trac_version, trac_tags
from bhdashboard.web_ui import DashboardModule

class ContainerWidget(WidgetBase):
    """Embed widgets positioned according to the rules defined by a layout.
    """
    def get_widget_params(self, name):
        """Return a dictionary containing arguments specification for
        the widget with specified name.
        """
        return {
                'layout' : {
                        'desc' : """Name of layout used to arrange widgets""",
                        'required' : True,
                    },
                'schema' : {
                        'desc' : """Widgets and position (in JSON)""",
                        'required' : True,
                        'type' : JsonField()
                    },
                'show_captions' : {
                        'desc' : """Show widget titles""",
                        'default' : False,
                    },
                'title' : {
                        'desc' : """User-defined title""",
                    },
            }
    get_widget_params = pretty_wrapper(get_widget_params, check_widget_name)

    def render_widget(self, name, context, options):
        """Count ocurrences of values assigned to given ticket field.
        """
        dbsys = DashboardSystem(self.env)
        params = ('layout', 'schema', 'show_captions', 'title')
        layout, schema, show_captions, title = \
                self.bind_params(name, options, *params)
        lp = dbsys.resolve_layout(layout)
        dbmod = DashboardModule(self.env)
        layout_data = lp.expand_layout(layout, context, 
                { 'schema' : schema, 'embed' : True })
        widgets = dbmod.expand_widget_data(context, schema)

        return layout_data['template'], \
                {
                    'title' : title,
                    'data' : dict(
                            context=context,
                            layout=schema,
                            widgets=widgets,
                            title='',
                            default={
                                    'height' : dbmod.default_widget_height or None
                                }
                        ),
                }, \
                context

    render_widget = pretty_wrapper(render_widget, check_widget_name)

