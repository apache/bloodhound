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

Widgets displaying report data.
"""

from cgi import parse_qs
from datetime import datetime, date, time
from itertools import count, imap, islice

from genshi.builder import tag
from trac.core import implements, TracError
from trac.mimeview.api import Context
from trac.resource import Resource, ResourceNotFound
from trac.ticket.query import Query, QueryModule
from trac.util.translation import _
from trac.web.api import RequestDone

from bhdashboard.util import WidgetBase, InvalidIdentifier, \
                              check_widget_name, dummy_request, \
                              merge_links, pretty_wrapper, trac_version, \
                              trac_tags

from multiproduct.env import ProductEnvironment

class TicketQueryWidget(WidgetBase):
    """Display tickets matching a TracQuery using a grid
    """
    def get_widget_params(self, name):
        """Return a dictionary containing arguments specification for
        the widget with specified name.
        """
        return {
                'query' : {
                        'desc' : """Query string""",
                        'required' : True,
                    },
                'max' : {
                        'default' : 0,
                        'desc' : """Limit the number of results displayed""",
                        'type' : int,
                },
                'page' : {
                        'desc' : """Page number""",
                        'type' : int,
                },
                'title' : {
                        'desc' : """Widget title""",
                },
            }
    get_widget_params = pretty_wrapper(get_widget_params, check_widget_name)

    def render_widget(self, name, context, options):
        """Execute custom query and render data using a grid
        """
        data = None
        req = context.req
        try:
            params = ('query', 'max', 'page', 'title')
            qstr, maxrows, page, title = self.bind_params(name, options, *params)

            fakereq = dummy_request(self.env, req.authname)
            fakereq.args = args = parse_qs(qstr)
            fakereq.arg_list = []
            for k,v in args.items():
                # Patch for 0.13
                fakereq.arg_list.extend((k, _v) for _v in v)
                try:
                    if len(v) == 1:
                        args[k] = v[0]
                except TypeError:
                    pass
            more_link_href = req.href('query', args)
            args.update({'page' : page, 'max': maxrows})

            qrymdl = self.env[QueryModule]
            if qrymdl is None :
                raise TracError('Query module not available (disabled?)')

            data = qrymdl.process_request(fakereq, self.env)[1]
        except TracError, exc:
            if data is not None:
                exc.title = data.get('title', 'TracQuery')
            raise
        else:
            qryctx = Context.from_request(fakereq)
            query = data['query']
            idxs = count()
            headers = [dict(title=h['label'], col=h['name'], hidden=False,
                            asc=h['name'] == query.order and not query.desc) \
                                for h in data['headers']]
            data.update(
                dict(header_groups=[headers],
                    numrows=len(data['tickets']),
                    row_groups=[(group_value, 
                            [{
                                '__color__' : t['priority_value'],
                                '__idx__' : idxs.next(),
                                'cell_groups' : [[
                                        {
                                            'header' : h,
                                            'index' : hidx,
                                            'value' : t[h['col']]
                                        } \
                                    for hidx, h in enumerate(headers)]],
                                'id' : t['id'],
                                'resource' : Resource('ticket', t['id']),
                                'href': t['href']
                            } for t in tickets]) \
                                for group_value, tickets in data['groups'] ]))
            return 'widget_grid.html', \
                    {
                        'title' : title or _('Custom Query'),
                        'data' : data,
                        'ctxtnav' : [
                                tag.a(_('More'), 
                                    href=more_link_href)],
                        'altlinks' : fakereq.chrome.get('links', {}).get('alternate')
                    }, \
                    qryctx

    render_widget = pretty_wrapper(render_widget, check_widget_name)

#--------------------------------------
# Query functions and methods
#--------------------------------------

def exec_query(env, req, qstr='status!=closed'):
    """ Perform a ticket query, returning a list of ticket ID's. 
    """
    return Query.from_string(env, qstr).execute(req)
