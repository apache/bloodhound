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

Widgets displaying timeline data.
"""

from itertools import imap, islice

from genshi.builder import tag
from trac.core import implements, TracError
from trac.ticket.api import TicketSystem
from trac.util.translation import _

from bhdashboard.api import DateField, EnumField, InvalidWidgetArgument, \
                            ListField
from bhdashboard.util import WidgetBase, check_widget_name, \
                              dummy_request, merge_links, minmax, \
                              pretty_wrapper, trac_version, trac_tags

class TicketFieldCloudWidget(WidgetBase):
    """Display a tag cloud representing frequency of values assigned to 
    ticket fields.
    """
    def get_widget_params(self, name):
        """Return a dictionary containing arguments specification for
        the widget with specified name.
        """
        return {
                'field' : {
                        'desc' : """Target ticket field""",
                        'required' : True,
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
            }
    get_widget_params = pretty_wrapper(get_widget_params, check_widget_name)

    def render_widget(self, name, context, options):
        """Count ocurrences of values assigned to given ticket field.
        """
        req = context.req
        params = ('field', 'verbose', 'threshold', 'max', 'title')
        fieldnm, verbose, threshold, maxitems, title = \
                self.bind_params(name, options, *params)
        tsys = self.env[TicketSystem]
        if tsys is None:
            raise TracError('Error loading ticket system (disabled?)')
        for field in tsys.get_ticket_fields():
            if field['name'] == fieldnm:
                break
        else:
            raise InvalidWidgetArgument('Unknown ticket field %s' % (fieldnm,))
        if field.get('custom'):
            sql = "SELECT value, count(value) FROM ticket_custom " \
                    "WHERE name='%(name)s' GROUP BY value"
        else:
            sql = "SELECT %(name)s, count(%(name)s) FROM ticket " \
                    "GROUP BY %(name)s"
        sql = sql % field
        # TODO : Implement threshold and max
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(sql)
        items = cursor.fetchall()

        QUERY_COLS = ['id', 'summary', 'owner', 'type', 'status', 'priority']
        item_link= lambda item: req.href.query(col=QUERY_COLS + [fieldnm], 
                                                **{fieldnm:item[0]})
        return 'widget_cloud.html', \
                {
                    'title' : title,
                    'data' : dict(
                            bounds=minmax(items, lambda x: x[1]),
                            item_link= item_link,
                            heading=_(fieldnm.capitalize()),
                            items=items,
                            verbose=verbose
                        ), 
                }, \
                context

    render_widget = pretty_wrapper(render_widget, check_widget_name)

