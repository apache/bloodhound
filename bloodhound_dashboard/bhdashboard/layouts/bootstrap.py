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

from trac.core import Component, implements, TracError
from trac.web.chrome import add_stylesheet

from bhdashboard.api import ILayoutProvider

class BootstrapLayout(Component):
    """Display a tag cloud representing frequency of values assigned to 
    ticket fields.
    """
    implements(ILayoutProvider)

    # ILayoutProvider methods
    def get_layouts(self):
        """Supported layouts.
        """
        yield 'bootstrap'

    def get_layout_description(self, name):
        """Return plain text description of the layout with specified name.
        """
        return "Bootstrap grid system " \
                "http://twitter.github.com/bootstrap/scaffolding.html#layouts"

    def expand_layout(self, name, context, options):
        """Specify bootstrap layout template
        """
        req = context.req
        add_stylesheet(req, 'dashboard/bootstrap.css')
        return {
              'template' : 'bootstrap.html',
            }

