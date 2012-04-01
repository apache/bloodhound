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

from datetime import datetime, date, time
from itertools import imap, islice

from genshi.builder import tag
from trac.core import implements, TracError
from trac.timeline.web_ui import TimelineModule
from trac.util.translation import _

from bhdashboard.api import DateField, EnumField, ListField
from bhdashboard.util import WidgetBase, InvalidIdentifier, \
                              check_widget_name, dummy_request, \
                              pretty_wrapper, trac_version, trac_tags

class TimelineWidget(WidgetBase):
    """Display activity feed.
    """
    def get_widget_params(self, name):
        """Return a dictionary containing arguments specification for
        the widget with specified name.
        """
        return {
                'from' : {
                        'desc' : """Display events before this date""",
                        'type' : DateField(), # TODO: Custom datetime format
                    },
                'daysback' : {
                        'desc' : """Event time window""",
                        'type' : int, 
                    },
                'precision' : {
                        'desc' : """Time precision""",
                        'type' : EnumField('second', 'minute', 'hour')
                    },
                'doneby' : {
                        'desc' : """Filter events related to user""",
                    },
                'filters' : {
                        'desc' : """Event filters""",
                        'type' : ListField()
                    },
                'max' : {
                        'default' : 0,
                        'desc' : """Limit the number of events displayed""",
                        'type' : int
                    },
            }
    get_widget_params = pretty_wrapper(get_widget_params, check_widget_name)

    def render_widget(self, name, context, options):
        """Gather timeline events and render data in compact view
        """
        data = None
        req = context.req
        try:
            params = ('from', 'daysback', 'doneby', 'precision', 'filters', \
                        'max')
            start, days, user, precision, filters, count = \
                    self.bind_params(name, options, *params)

            mockreq = dummy_request(self.env, req.authname)
            mockreq.args = {
                    'author' : user or '',
                    'daysback' : days or '',
                    'max' : count,
                    'precision' : precision,
                    'user' : user
                }
            if start is not None:
                mockreq.args['from'] = start.strftime('%x %X')

            timemdl = self.env[TimelineModule]
            if timemdl is None :
                raise TracError('Timeline module not available (disabled?)')

            data = timemdl.process_request(mockreq)[1]
        except TracError, exc:
            if data is not None:
                exc.title = data.get('title', 'TracReports')
            raise
        else:
            return 'widget_timeline.html', \
                    {
                        'title' : _('Activity'),
                        'data' : data
                    }, \
                    context

    render_widget = pretty_wrapper(render_widget, check_widget_name)

