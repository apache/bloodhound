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

Widgets displaying ticket data.
"""

from uuid import uuid4

from trac.core import Component, implements, TracError
from trac.web.chrome import add_stylesheet, add_script

from bhdashboard.api import ILayoutProvider

class BootstrapLayout(Component):
    """Implement some basic bootstrap layouts
    """
    implements(ILayoutProvider)

    # ILayoutProvider methods
    def get_layouts(self):
        """Supported layouts.
        """
        yield 'bootstrap_grid'
        yield 'bootstrap_btnbar'

    def get_layout_description(self, name):
        """Return plain text description of the layout with specified name.
        """
        return { 
                'bootstrap_grid' : "Bootstrap grid system " \
                    "http://twitter.github.com/bootstrap/scaffolding.html#layouts",
                'bootstrap_btnbar' : "Button toolbar acting as tabs nav"
            }[name]

    def expand_layout(self, name, context, options):
        """Specify bootstrap layout template
        """
        req = context.req
        add_stylesheet(req, 'dashboard/css/bootstrap.css')
        add_stylesheet(req, 'dashboard/css/bootstrap-responsive.css')

        if name == 'bootstrap_btnbar':
            self._process_btnbar(req, options)

        results = {
                ('bootstrap_grid', False) : {
                        'template' : 'bs_grid_full.html',
                    },
                ('bootstrap_grid', True) : {
                        'template' : 'bs_grid.html',
                    },
                ('bootstrap_btnbar', False) : {
                        'template' : 'bs_btnbar_full.html',
                    },
                ('bootstrap_btnbar', True) : {
                        'template' : 'bs_btnbar.html',
                    },
            }
        return results[( name , bool(options.get('embed')) )]

    # Internal methods
    def _process_btnbar(self, req, options):
        """Determine toolbar groups
        """
        layout_data = options['schema']
        orig_tb = layout_data.get('toolbar', [])
        ready = layout_data.get('ready')
        if not ready:
            layout_data['toolbar'] = tb = [[]]
            last_group = tb[0]
            active = layout_data.get('active')
            for i, (caption, idx) in enumerate(orig_tb):
                if caption == '|' :
                    last_group = []
                    tb.append(last_group)
                else:
                    last_group.append(
                            { 'caption' : caption, 'widget' :idx, 
                              'id' : uuid4().hex, 'active' : i == active })
        layout_data['ready'] = True

