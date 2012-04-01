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
from trac.ticket.report import ReportModule
from trac.util.translation import _

from bhdashboard.util import WidgetBase, InvalidIdentifier, \
                              check_widget_name, pretty_wrapper

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
                'limit' : {
                        'default' : 0,
                        'desc' : """Number of results to retrieve""",
                        'type' : int,
                },
            }
    get_widget_params = pretty_wrapper(get_widget_params, check_widget_name)

    def render_widget(self, name, context, options):
        """Execute stored report and render data using a grid
        """
        metadata = data = None
        req = context.req
        try:
            rptid, limit = self.bind_params(name, options, 'id', 'limit')
            metadata = self.get(req, rptid)
            # TODO: Should metadata also contain columns definition ?
            data = list(self.execute(req, rptid, limit))
        except TracError, exc:
            if metadata is not None :
                exc.title = metadata.get('title', 'TracReports')
            else:
                exc.title = 'TracReports'
            raise
        else:
            title = metadata.get('title', '%s #%s' % (_('Report'), rptid))
            return 'widget_grid.html', \
                    {
                        'title' : tag.a(title, href=req.href('report', rptid)),
                        'data' : data
                    }, \
                    context

    render_widget = pretty_wrapper(render_widget, check_widget_name)

    # Internal methods

    # These have been imported verbatim from existing 
    # `tracgviz.rpc.ReportRPC` class in TracGViz plugin ;)
    def get(self, req, id):
        r"""Return information about an specific report as a dict 
        containing the following fields.
        
        - id :            the report ID.
        - title:          the report title.
        - description:    the report description.
        - query:          the query string used to select the tickets 
                          to be included in this report. This field 
                          is returned only if `REPORT_SQL_VIEW` has 
                          been granted to the client performing the 
                          request. Otherwise it is empty.
        """
        sql = "SELECT id,title,query,description from report " \
                "WHERE id=%s" % (id,)
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        try:
            cursor.execute(sql)
            for report_info in cursor:
                return dict(zip(['id','title','query','description'], report_info))
            else:
                return None
        finally:
            cursor.close()

    def _execute_sql(self, req, id, sql, limit=0):
        r"""Execute a SQL report and return no more than `limit` rows 
        (or all rows if limit == 0).
        """
        repmdl = ReportModule(self.env)
        db = self.env.get_db_cnx()
        try:
            args = repmdl.get_var_args(req)
        except ValueError,e:
            raise ValueError(_('Report failed: %(error)s', error=e))
        try:
            try:
                # Paginated exec (>=0.11)
                exec_proc = repmdl.execute_paginated_report
                kwargs = dict(limit=limit)
            except AttributeError:
                # Legacy exec (<=0.10)
                if limit > 0:
                    exec_proc = lambda *args, **kwargs: \
                        islice(repmdl.execute_report(*args, **kwargs), limit)
                else:
                    exec_proc = repmdl.execute_report
                kwargs = {}
            return exec_proc(req, db, id, sql, args, **kwargs)[:2]
        except Exception, e:
            db.rollback()
            raise 

    def execute(self, req, id, limit=0):
        r"""Execute a Trac report.

        @param id     the report ID.
        @return       a list containing the data provided by the 
                      target report.
        @throws       `NotImplementedError` if the report definition 
                      consists of saved custom query specified 
                      using a URL.
        @throws       `QuerySyntaxError` if the report definition 
                      consists of a `TracQuery` containing syntax errors.
        @throws       `Exception` in case of detecting any other error.
        """
        report_spec = self.get(req, id)
        if report_spec is None:
            raise InvalidIdentifier('Report %s does not exist' % (id,))
        sql = report_spec['query']
        query = ''.join([line.strip() for line in sql.splitlines()])
        if query and (query[0] == '?' or query.startswith('query:?')):
            raise NotImplementedError('Saved custom queries specified ' \
                                  'using URLs are not supported.')
        elif query.startswith('query:'):
            query = Query.from_string(self.env, query[6:], report=id)
            server_url = urlparse(req.base_url)
            server_href = Href(urlunparse((server_url.scheme, \
                                        server_url.netloc, \
                                        '', '', '', '')))
            def rel2abs(row):
                """Turn relative value in 'href' into absolute URLs."""
                self.log.debug('IG: Query Row %s', row)
                url = row['href']
                urlobj = urlparse(url)
                if not urlobj.netloc:
                    row['href'] = server_href(url)
                return row
            
            return imap(rel2abs, query.execute(req))
        else:
            cols, results = self._execute_sql(req, id, sql, limit=limit)
            return (dict(zip(cols, list(row))) for row in results)

