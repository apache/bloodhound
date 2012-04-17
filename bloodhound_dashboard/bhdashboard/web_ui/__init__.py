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
from trac.web.api import IRequestHandler, IRequestFilter
from trac.web.chrome import add_ctxtnav, add_stylesheet, Chrome, \
                            INavigationContributor, ITemplateProvider

from bhdashboard.api import DashboardSystem
from bhdashboard import _json

class DashboardModule(Component):
    """Web frontend for dashboard infrastructure.
    """
    implements(IRequestHandler, IRequestFilter, INavigationContributor, \
                ITemplateProvider)

    mainnav_label = Option('dashboard', 'mainnav', 'Dashboard', \
                            """Dashboard label in mainnav""")
    default_widget_height = IntOption('widgets', 'default_height', 320, \
                            """Default widget height in pixels""")

    # IRequestFilter methods

    def pre_process_request(self, req, handler):
        """Always returns the request handler unchanged.
        """
        return handler

    def post_process_request(self, req, template, data, content_type):
        """Inject dashboard helpers in data.
        """
        if data is not None :
            data['bhdb'] = DashboardChrome(self.env)
        return template, data, content_type

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
        template, layout_data = self.expand_layout_data(req, 
            'bootstrap_grid', self.DASHBOARD_SCHEMA)
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
                 ('layouts', resource_filename('bhdashboard.layouts', 'htdocs'))
                 ]

    def get_templates_dirs(self):
        """List `templates` folders for dashboard and widgets.
        """
        resource_filename = pkg_resources.resource_filename
        return [resource_filename('bhdashboard.layouts', 'templates'),
                resource_filename('bhdashboard.web_ui', 'templates'),
                resource_filename('bhdashboard.widgets', 'templates')]

    # Temp vars
    DASHBOARD_SCHEMA = {
            'div' : [
                    {
                        '_class' : 'row',
                        'div' : [
                                {
                                    '_class' : 'span8',
                                    'widgets' : [0]
                                },
                                {
                                    '_class' : 'span4',
                                    'widgets' : [1]
                                }
                            ]
                    }
                ],
            'widgets' : {
                    0: {
                        'args' : ['Container', None, 
                                {'args' : {'layout' : 'bootstrap_btnbar',
                                        'schema' : '''
                                        {
                                          "toolbar" : [
                                              ["Products", null],
                                              ["My Tickets", "w3"],
                                              ["All tickets", "w2"],
                                              ["|", null],
                                              ["Projects", null],
                                              ["Components", "w1"]
                                            ],
                                          "active" : 1,
                                          "widgets" : {
                                            "w1" : {
                                              "args" : [
                                                  "TicketFieldCloud", 
                                                  null, 
                                                  {"args" : {
                                                      "field" : "component",
                                                      "verbose" : true}}]
                                            },
                                            "w2" : {
                                              "args" : [
                                                  "TicketQuery", null, 
                                                  {"args" : {
                                                      "max" : 10,
                                                      "query" : "''' + 
                'status!=closed&group=time&col=id&col=summary&col=owner' \
                '&col=status&col=priority&order=priority&groupdesc=1&desc=1' +
                                                      '''",
                                                      "title" : "All Tickets"}
                                                  }],
                                              "altlinks" : false
                                            },
                                            "w3" : {
                                              "args" : [
                                                  "TicketQuery", null, 
                                                  {"args" : {
                                                      "max" : 10,
                                                      "query" : "''' + 
                'status!=closed&group=time&col=id&col=summary&col=owner' \
                '&col=status&col=priority&order=priority&groupdesc=1&desc=1' \
                '&owner=$USER' +
                                                      '''",
                                                      "title" : "My Tickets"}
                                                  }],
                                              "altlinks" : false
                                            }
                                          }
                                        }
                                        ''',
                                        'title' : _("Dashboard")
                                        }
                                }]
                    },
                    1: {
                        'args' : ['Timeline', None, {'args' : {}}]
                    },
               }
        }

    # Public API
    def expand_layout_data(self, req, layout_name, schema, embed=False):
        """Determine the template needed to render a specific layout
        and the data needed to place the widgets at expected
        location.
        """
        layout = DashboardSystem(self.env).resolve_layout(layout_name)

        ctx = Context.from_request(req)
        template = layout.expand_layout(layout_name, ctx, {
                'schema' : schema,
                'embed' : embed
            })['template']
        return template, schema

    def expand_widget_data(self, req, schema):
        """Expand raw widget data and format it for use in template
        """
        # TODO: Implement dynamic dashboard specification
        widgets_spec = schema.pop('widgets', {})
        widgets_index = dict([wnm, wp] \
                for wp in DashboardSystem(self.env).widget_providers \
                for wnm in wp.get_widgets()
            )
        self.log.debug("Bloodhound: Widget index %s" % (widgets_index,))
        ctx = Context.from_request(req)
        for w in widgets_spec.itervalues():
            w['c'] = widgets_index[w['args'][0]]
            w['args'][1] = ctx
        self.log.debug("Bloodhound: Widget specs %s" % (widgets_spec,))
        chrome = Chrome(self.env)
        render = chrome.render_template
        data_strm = ( (k, w, w['c'].render_widget(*w['args'])) \
                for k,w in widgets_spec.iteritems())
        return dict([k, {'title' : data['title'], 
                'content' : render(wctx.req, template, data['data'], fragment=True),
                'ctxtnav' : w.get('ctxtnav', True) and data.get('ctxtnav') or None, 
                'altlinks' : w.get('altlinks', True) and data.get('altlinks') or None}] \
                for k, w, (template, data, wctx) in data_strm)

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
        template, layout_data = dbmod.expand_layout_data(
                context.req, layout, schema, True)
        widgets = dbmod.expand_widget_data(context.req, layout_data)
        return Chrome(self.env).render_template(context.req, template, 
                dict(context=context, layout=layout_data, 
                        widgets=widgets, title='',
                        default={'height':dbmod.default_widget_height or None}),
                fragment=True)

    def expand_widget(self, context, widget):
        """Render single widget

        :param context: Rendering context
        :param widget: Widget definition
        """
        dbmod = DashboardModule(self.env)
        if isinstance(widget['args'], basestring):
            widget['args'] = _json.loads(widget['args'])
        return dbmod.expand_widget_data(
                    context.req,
                    {'widgets' : { 0 : widget }}
                )[0]

#------------------------------------------------------
#    Stream processors
#------------------------------------------------------

def parse_widgets_markup(stream):
    """Parse Genshi Markup for a set of widgets
    """
    s = iter(stream)

    # Check that stream starts by opening bh:widgets tag
    token, data, pos = s.next()
    assert token == 'START'
    assert data[0].namespace == XMLNS_DASHBOARD_UI
    assert data[1].localname == 'widgets'

    # Continue parsing bh:w tag
    def find(_s, tkn, ns, localname):
        for token, data, pos in _s:
            if token == tkn and data[0].namespace != ns \
                    and data[1].localname != localname:
                return token, data, pos
        else:
            return None

    i = find(s, 'START', XMLNS_DASHBOARD_UI, 'widget')

    # TODO: Finish parsing widgets markup

    #if i is not None:
    #    i = find()

def parse_widget_markup(stream):
    """Parse Genshi Markup for a single widget
    """

