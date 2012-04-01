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

from datetime import datetime, date, time
from itertools import imap, islice

from genshi.builder import tag
from trac.core import implements, TracError
from trac.mimeview.api import Context
from trac.resource import ResourceNotFound
from trac.ticket.report import ReportModule
from trac.util.translation import _
from trac.web.api import RequestDone

from bhdashboard.util import WidgetBase, InvalidIdentifier, \
                              check_widget_name, dummy_request, \
                              merge_links, pretty_wrapper, trac_version, \
                              trac_tags

class TicketReportWidget(WidgetBase):
    """Display tickets in saved report using a grid
    """
    def get_widget_params(self, name):
        """Return a dictionary containing arguments specification for
        the widget with specified name.
        """
        return {
                'id' : {
                        'desc' : """Report number""",
                        'required' : True,
                        'type' : int,
                    },
                'page' : {
                        'default' : 1,
                        'desc' : """Retrieve results in given page.""",
                        'type' : int,
                },
                'user' : {
                        'desc' : """Render the report for a given user.""",
                },
            }
    get_widget_params = pretty_wrapper(get_widget_params, check_widget_name)

    def render_widget(self, name, context, options):
        """Execute stored report and render data using a grid
        """
        data = None
        req = context.req
        try:
            params = ('id', 'page', 'user')
            rptid, page, user = self.bind_params(name, options, *params)
            user = user or req.authname

            fakereq = dummy_request(self.env, req.authname)
            fakereq.args = {'page' : page, 'user' : user}
            del fakereq.redirect     # raise RequestDone as usual

            rptmdl = self.env[ReportModule]
            if rptmdl is None :
                raise TracError('Report module not available (disabled?)')
            if trac_version < trac_tags[0]:
                args = fakereq, self.env.get_db_cnx(), rptid
            else:
                args = fakereq, rptid
            data = rptmdl._render_view(*args)[1]
        except ResourceNotFound, exc:
            raise InvalidIdentifier(unicode(exc))
        except RequestDone:
            raise TracError('Cannot execute report. Redirection needed')
        except TracError, exc:
            if data is not None:
                exc.title = data.get('title', 'TracReports')
            raise
        else:
            title = data.get('title', '%s {%s}' % (_('Report'), rptid))
            rptctx = Context.from_request(fakereq, 'report', rptid)
            return 'widget_grid.html', \
                    {
                        'title' : title,
                        'data' : data,
                        'ctxtnav' : [
                            tag.a(_('More'), href=req.href('report', rptid)),
                            ('REPORT_MODIFY' in req.perm(rptctx.resource)) and \
                                tag.a(_('Edit'), href=req.href('report', rptid, action='edit')) or None,
                            ],
                        'altlinks' : fakereq.chrome.get('links', {}).get('alternate')
                    }, \
                    rptctx

    render_widget = pretty_wrapper(render_widget, check_widget_name)

