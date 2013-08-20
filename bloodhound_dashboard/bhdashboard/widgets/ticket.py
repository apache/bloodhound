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

from itertools import imap, islice
from urllib import urlencode

from genshi.builder import tag
from genshi.core import Markup
from trac.core import implements, TracError
from trac.ticket.api import TicketSystem
from trac.ticket.query import Query
from trac.ticket.roadmap import apply_ticket_permissions, get_ticket_stats, \
                            ITicketGroupStatsProvider, RoadmapModule
from trac.util.text import unicode_urlencode
from trac.util.translation import _
from trac.web.chrome import add_stylesheet

from bhdashboard.api import DateField, EnumField, InvalidWidgetArgument, \
                            ListField
from bhdashboard.widgets.query import exec_query
from bhdashboard.util import WidgetBase, check_widget_name, \
                            dummy_request, merge_links, minmax, \
                            pretty_wrapper, resolve_ep_class, \
                            trac_version, trac_tags

from multiproduct.env import Product, ProductEnvironment

class TicketFieldValuesWidget(WidgetBase):
    """Display a tag cloud representing frequency of values assigned to 
    ticket fields.
    """
    DASH_ITEM_HREF_MAP = {'milestone': ('milestone',),
                         }
                     
    def get_widget_params(self, name):
        """Return a dictionary containing arguments specification for
        the widget with specified name.
        """
        return {
                'field' : {
                        'desc' : """Target ticket field. """
                                """Required if no group in `query`.""",
                    },
                'query' : {
                        'desc' : """TracQuery used to filter target tickets.""",
                    },
                'title' : {
                        'desc' : """Widget title""",
                    },
                'verbose' : {
                        'desc' : """Show frequency next to each value""",
                        'default' : False,
                        'type' : bool, 
                    },
                'threshold' : {
                        'desc' : """Filter items having smaller frequency""",
                        'type' : int,
                    },
                'max' : {
                        'default' : 0,
                        'desc' : """Limit the number of items displayed""",
                        'type' : int
                    },
                'view' : {
                        'desc' : """Display mode. Should be one of the following

                            - `list` : Unordered value list (default)
                            - `cloud` : Similar to tag cloud
                            """,
                        'default' : 'list',
                        'type' : EnumField('list', 'cloud', 'table', 'compact'),
                    },
            }
    get_widget_params = pretty_wrapper(get_widget_params, check_widget_name)

    def render_widget(self, name, context, options):
        """Count ocurrences of values assigned to given ticket field.
        """
        req = context.req
        params = ('field', 'query', 'verbose', 'threshold', 'max', 'title',
                  'view')
        fieldnm, query, verbose, threshold, maxitems, title, view = \
                self.bind_params(name, options, *params)
        
        field_maps = {'type': {'admin_url': 'type',
                               'title': 'Types',
                               },
                      'status': {'admin_url': None,
                                 'title': 'Statuses',
                                 },
                      'priority': {'admin_url': 'priority',
                                   'title': 'Priorities',
                                   },
                      'milestone': {'admin_url': 'milestones',
                                    'title': 'Milestones',
                                    },
                      'component': {'admin_url': 'components',
                                    'title': 'Components',
                                    },
                      'version': {'admin_url': 'versions',
                                  'title': 'Versions',
                                  },
                      'severity': {'admin_url': 'severity',
                                   'title': 'Severities',
                                   },
                      'resolution': {'admin_url': 'resolution',
                                     'title': 'Resolutions',
                                     },
                      }
        _field = []
        def check_field_name():
            if fieldnm is None:
                raise InvalidWidgetArgument('field', 'Missing ticket field')
            tsys = self.env[TicketSystem]
            if tsys is None:
                raise TracError(_('Error loading ticket system (disabled?)'))
            for field in tsys.get_ticket_fields():
                if field['name'] == fieldnm:
                    _field.append(field)
                    break
            else:
                if fieldnm in field_maps:
                    admin_suffix = field_maps.get(fieldnm)['admin_url']
                    if 'TICKET_ADMIN' in req.perm and admin_suffix is not None:
                        hint = _('You can add one or more '
                                 '<a href="%(url)s">here</a>.',
                                url=req.href.admin('ticket', admin_suffix))
                    else:
                        hint = _('Contact your administrator for further details')
                    return 'widget_alert.html', \
                            {
                                'title' : Markup(_('%(field)s',
                                            field=field_maps[fieldnm]['title'])),
                                'data' : dict(msgtype='info',
                                    msglabel="Note",
                                    msgbody=Markup(_('''No values are
                                        defined for ticket field
                                        <em>%(field)s</em>. %(hint)s''',
                                        field=fieldnm, hint=hint))
                                    )
                            }, context
                else:
                    raise InvalidWidgetArgument('field', 
                            'Unknown ticket field %s' % (fieldnm,))
            return None
        
        if query is None :
            data = check_field_name()
            if data is not None:
                return data
            field = _field[0]
            if field.get('custom'):
                sql = "SELECT COALESCE(value, ''), count(COALESCE(value, ''))" \
                        " FROM ticket_custom " \
                        " WHERE name='%(name)s' GROUP BY COALESCE(value, '')"
            else:
                sql = "SELECT COALESCE(%(name)s, ''), " \
                        "count(COALESCE(%(name)s, '')) FROM ticket " \
                        "GROUP BY COALESCE(%(name)s, '')"
            sql = sql % field
            # TODO : Implement threshold and max

            db_query = req.perm.env.db_query \
                if isinstance(req.perm.env, ProductEnvironment) \
                else req.perm.env.db_direct_query
            with db_query as db:
                cursor = db.cursor()
                cursor.execute(sql)
                items = cursor.fetchall()

            QUERY_COLS = ['id', 'summary', 'owner', 'type', 'status', 'priority']
            item_link= lambda item: req.href.query(col=QUERY_COLS + [fieldnm], 
                                                    **{fieldnm:item[0]})
        else:
            query = Query.from_string(self.env, query, group=fieldnm)
            if query.group is None:
                data = check_field_name()
                if data is not None:
                    return data
                raise InvalidWidgetArgument('field', 
                        'Invalid ticket field for ticket groups')

            fieldnm = query.group
            sql, v = query.get_sql() 
            sql = "SELECT COALESCE(%(name)s, '') , count(COALESCE(%(name)s, ''))"\
                    "FROM (%(sql)s) AS foo GROUP BY COALESCE(%(name)s, '')" % \
                    { 'name' : fieldnm, 'sql' : sql }
            db = self.env.get_db_cnx()
            try :
                cursor = db.cursor()
                cursor.execute(sql, v)
                items = cursor.fetchall()
            finally:
                cursor.close()

            query_href = query.get_href(req.href)
            item_link= lambda item: query_href + \
                    '&' + unicode_urlencode([(fieldnm, item[0])])

        if fieldnm in self.DASH_ITEM_HREF_MAP:
            def dash_item_link(item):
                if item[0]:
                    args = self.DASH_ITEM_HREF_MAP[fieldnm] + (item[0],)
                    return req.href(*args)
                else:
                    return item_link(item)
        else:
            dash_item_link = item_link

        if title is None:
            heading = _(fieldnm.capitalize())
        else:
            heading = None

        return 'widget_cloud.html', \
                {
                    'title' : title,
                    'data' : dict(
                            bounds=minmax(items, lambda x: x[1]),
                            item_link=dash_item_link,
                            heading=heading,
                            items=items,
                            verbose=verbose,
                            view=view,
                        ), 
                }, \
                context

    render_widget = pretty_wrapper(render_widget, check_widget_name)

class TicketGroupStatsWidget(WidgetBase):
    """Display progress bar illustrating statistics gathered on a group
    of tickets.
    """
    def get_widget_params(self, name):
        """Return a dictionary containing arguments specification for
        the widget with specified name.
        """
        return {
                'query' : {
                        'default' : 'status!=closed',
                        'desc' : """Query string""",
                    },
                'stats_provider' : {
                        'desc' : """Name of the component implementing
        `ITicketGroupStatsProvider`, which is used to collect statistics 
        on groups of tickets.""",
                        'default' : 'DefaultTicketGroupStatsProvider'
                    },
                'skin' : {
                        'desc' : """Look and feel of the progress bar""",
                        'type' : EnumField('info', 'success', 'warning', 
                                'danger',
                                'info-stripped', 'success-stripped', 
                                'warning-stripped', 'danger-stripped')
                    },
                'title' : {
                        'desc' : """Widget title""",
                    },
                'legend' : {
                        'desc' : """Text on top of the progress bar""",
                    },
                'desc' : {
                        'desc' : """Descriptive (wiki) text""",
                    },
                'view' : {
                        'desc' : """Display mode to render progress info""",
                        'type' : EnumField('compact', 'standard')
                    },
            }
    get_widget_params = pretty_wrapper(get_widget_params, check_widget_name)

    def render_widget(self, name, context, options):
        """Prepare ticket stats
        """
        req = context.req
        params = ('query', 'stats_provider', 'skin', 'title', 'legend', 'desc',
                'view')
        qstr, pnm, skin, title, legend, desc, view = \
                self.bind_params(name, options, *params)
        statsp = resolve_ep_class(ITicketGroupStatsProvider, self, pnm,
                                    default=RoadmapModule(self.env).stats_provider)
        if skin is not None :
            skin = (skin or '').split('-', 2)

        tickets = exec_query(self.env, req, qstr)
        tickets = apply_ticket_permissions(self.env, req, tickets)
        stat = get_ticket_stats(statsp, tickets)

        add_stylesheet(req, 'dashboard/css/bootstrap.css')
        add_stylesheet(req, 'dashboard/css/bootstrap-responsive.css')
        add_stylesheet(req, 'dashboard/css/roadmap.css')
        return 'widget_progress.html', \
                {
                    'title' : title,
                    'data' : dict(
                            desc=desc, legend=legend, bar_styles=skin,
                            stats=stat, view=view,
                        ), 
                }, \
                context

    render_widget = pretty_wrapper(render_widget, check_widget_name)
