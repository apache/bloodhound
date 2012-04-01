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

from itertools import izip
import pkg_resources
import re

from genshi.builder import tag
from trac.core import Component, implements
from trac.config import Option, IntOption
from trac.mimeview.api import Context
from trac.util.translation import _
from trac.ticket.query import QueryModule
from trac.ticket.report import ReportModule
from trac.util.compat import groupby
from trac.web.api import IRequestHandler
from trac.web.chrome import add_ctxtnav, add_stylesheet, Chrome, \
                            INavigationContributor, ITemplateProvider

from bhdashboard.api import DashboardSystem

class DashboardModule(Component):
    implements(IRequestHandler, INavigationContributor, ITemplateProvider)

    mainnav_label = Option('dashboard', 'mainnav', 'Dashboard', \
                            """Dashboard label in mainnav""")
    default_widget_height = IntOption('widgets', 'default_height', 320, \
                            """Default widget height in pixels""")

    # IRequestHandler methods
    def match_request(self, req):
        """Match dashboard prefix"""
        return bool(re.match(r'^/dashboard(/.)?', req.path_info))

    def process_request(self, req):
        """Initially this will render static widgets. With time it will be 
        more and more dynamic and flexible.
        """
        if self.env[QueryModule] is not None:
            add_ctxtnav(req, _('Custom Query'), req.href.query())
        if self.env[ReportModule] is not None:
            add_ctxtnav(req, _('Reports'), req.href.report())
        template, layout_data = self.expand_layout_data(req)
        widgets = self.expand_widget_data(req, layout_data) 
        return template, {
                    'context' : Context.from_request(req),
                    'layout' : layout_data,
                    'widgets' : widgets,
                    'title' : _(self.mainnav_label),
                    'default' : {
                            'height' : self.default_widget_height or None
                        }
                }, None

    # INavigationContributor methods
    def get_active_navigation_item(self, req):
        """Highlight dashboard mainnav item.
        """
        return 'dashboard'

    def get_navigation_items(self, req):
        """Add an item in mainnav to access global dashboard
        """
        if 'DASHBOARD_VIEW' in req.perm:
            yield ('mainnav', 'dashboard', 
                    tag.a(_(self.mainnav_label), href=req.href.dashboard()))

    # ITemplateProvider methods
    def get_htdocs_dirs(self):
        """List `htdocs` dirs for dashboard and widgets.
        """
        resource_filename = pkg_resources.resource_filename
        return [
                 ('dashboard', resource_filename('bhdashboard', 'htdocs')),
                 #('widgets', resource_filename('bhdashboard.widgets', 'htdocs'))
                 ]

    def get_templates_dirs(self):
        """List `templates` folders for dashboard and widgets.
        """
        resource_filename = pkg_resources.resource_filename
        return [resource_filename('bhdashboard.layouts', 'templates'),
                resource_filename('bhdashboard.widgets', 'templates')]

    # Public API
    def expand_layout_data(self, req):
        """Determine the template needed to render a specific layout
        and the data needed to place the widgets at expected
        location.

        Notes: So far it only renders a few widgets and there's no
        chance to customize this view at all.
        """
        # TODO: Retrieve layout definition from somewhere
        from bhdashboard.layouts.bootstrap import BootstrapLayout
        from bhdashboard.widgets.query import TicketQueryWidget
        from bhdashboard.widgets.ticket import TicketFieldCloudWidget
        from bhdashboard.widgets.timeline import TimelineWidget

        dashboard_query = 'status=accepted&status=assigned&status=new' \
                '&status=reopened&group=time&col=id&col=summary&col=owner' \
                '&col=status&col=priority&order=priority&groupdesc=1&desc=1'
        layout = BootstrapLayout(self.env)
        schema = {
                'div' : [
                        {
                            '_class' : 'row',
                            'div' : [
                                    {
                                        '_class' : 'span8',
                                        'widgets' : [0,2]
                                    },
                                    {
                                        '_class' : 'span4',
                                        'widgets' : [1]
                                    }
                                ]
                        }
                    ],
                'widgets' : [
                        {
                            'args' : ['TicketQuery', None, 
                                    {'args' : {'max' : 10,
                                            'query' : dashboard_query,
                                            'title' : 'Dashboard'}
                                    }],
                            'altlinks' : False
                        },
                        {
                            'args' : ['Timeline', None, {'args' : {}}]
                        },
                        {
                            'args' : ['Container', None, 
                                    {'args' : {'layout' : 'bootstrap_grid',
                                            'schema' : """
                                            {
                                              "div" : [{
                                                "_class" : "row",
                                                "div" : [{
                                                    "_class" : "span3",
                                                    "widgets" : [0]
                                                  },
                                                  {
                                                    "_class" : "span5",
                                                    "widgets" : [1]
                                                  }]
                                                }],
                                              "widgets" : [
                                                {
                                                  "args" : [
                                                      "TicketFieldCloud", 
                                                      null, 
                                                      {"args" : {
                                                          "field" : "component",
                                                          "verbose" : true}}]
                                                },
                                                {
                                                  "args" : [
                                                      "TicketFieldCloud", 
                                                      null, 
                                                      {"args" : {
                                                          "field" : "type",
                                                          "verbose" : true}}]
                                                }
                                              ]
                                            }
                                            """
                                            }
                                    }]
                        },
                    ]
            }

        ctx = Context.from_request(req)
        template = layout.expand_layout('bootstrap_grid', ctx, {
                'schema' : schema
            })['template']
        return template, schema

    def expand_widget_data(self, req, schema):
        """Expand raw widget data and format it for use in template

        Notes: So far it only renders a few widgets and there's no
        chance to customize this view at all.
        """
        # TODO: Implement dynamic dashboard specification
        widgets_spec = schema.pop('widgets', [])
        widgets_index = dict([k, list(v)] for k,v in \
                groupby(widgets_spec, lambda w : w['args'][0]))
        ctx = Context.from_request(req)
        for wp in DashboardSystem(self.env).widget_providers:
            for wnm in wp.get_widgets():
                substitutions = widgets_index.pop(wnm, [])
                i = -1
                for i, w in enumerate(substitutions):
                    w['c'] = wp
                    w['args'][1] = ctx
                self.log.debug('Widget %s (%s substitutions)', wnm, i + 1)
        if len(widgets_index) > 0:
            raise LookupError('Unknown provider for widgets %s', 
                    ' , '.join(widgets_index.keys()))
        chrome = Chrome(self.env)
        render = chrome.render_template
        data_strm = (w['c'].render_widget(*w['args']) for w in widgets_spec)
        return [{'title' : data['title'], 
                'content' : render(wctx.req, template, data['data'], fragment=True),
                'ctxtnav' : w.get('ctxtnav', True) and data.get('ctxtnav') or None, 
                'altlinks' : w.get('altlinks', True) and data.get('altlinks') or None} \
                for w, (template, data, wctx) in izip(widgets_spec, data_strm)]

