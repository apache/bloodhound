
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

""" Multi product support for ticket queries."""

from __future__ import with_statement

from itertools import groupby
from math import ceil
from datetime import datetime, timedelta

from genshi.builder import tag

from trac.core import TracError
from trac.db import get_column_names
from trac.mimeview.api import Mimeview
from trac.ticket.api import TicketSystem
from trac.ticket.query import Query, QueryModule, TicketQueryMacro, QueryValueError
from trac.util.datefmt import from_utimestamp, utc, to_timestamp
from trac.util.text import shorten_line
from trac.util.translation import _, tag_
from trac.web import parse_arg_list, arg_list_to_args
from trac.web.chrome import Chrome, add_stylesheet, add_link, web_context, \
    add_script_data, add_script, add_ctxtnav, add_warning
from trac.resource import Resource

from multiproduct.dbcursor import GLOBAL_PRODUCT
from multiproduct.env import lookup_product_env, resolve_product_href, \
    ProductEnvironment


class ProductQuery(Query):
    """Product Overrides for TracQuery.
    
    This class allows for writing TracQuery expressions matching resources
    beyond product boundaries.
    """
    
    def _count(self, sql, args):
        cnt = self.env.db_direct_query("SELECT COUNT(*) FROM (%s) AS x"
                                % sql, args)[0][0]
        # "AS x" is needed for MySQL ("Subqueries in the FROM Clause")
        self.env.log.debug("Count results in Query: %d", cnt)
        return cnt

    def get_columns(self):
        super(ProductQuery, self).get_columns()
        if not 'product' in self.cols and self.group != 'product':
            # make sure 'product' is always present 
            # (needed for product context, href, permission checks ...)
            # but don't implicitly include it if items are grouped by product
            self.cols.insert(0, 'product')
        return self.cols

    def _get_ticket_href(self, prefix, tid):
        product_env = ProductEnvironment(self.env, prefix)
        return product_env.href.ticket(tid)

    def execute(self, req=None, db=None, cached_ids=None, authname=None,
                tzinfo=None, href=None, locale=None):
        """Retrieve the list of matching tickets.

        :since 1.0: the `db` parameter is no longer needed and will be removed
        in version 1.1.1
        """
        if req is not None:
            href = req.href
        with self.env.db_direct_query as db:
            cursor = db.cursor()

            self.num_items = 0
            sql, args = self.get_sql(req, cached_ids, authname, tzinfo, locale)
            if sql.startswith('SELECT ') and not sql.startswith('SELECT DISTINCT '):
                sql = 'SELECT DISTINCT * FROM (' + sql + ') AS subquery'
            self.num_items = self._count(sql, args)

            if self.num_items <= self.max:
                self.has_more_pages = False

            if self.has_more_pages:
                max = self.max
                if self.group:
                    max += 1
                sql = sql + " LIMIT %d OFFSET %d" % (max, self.offset)
                if (self.page > int(ceil(float(self.num_items) / self.max)) and
                    self.num_items != 0):
                    raise TracError(_("Page %(page)s is beyond the number of "
                                      "pages in the query", page=self.page))

            # self.env.log.debug("SQL: " + sql % tuple([repr(a) for a in args]))
            cursor.execute(sql, args)
            columns = get_column_names(cursor)
            fields = []
            for column in columns:
                fields += [f for f in self.fields if f['name'] == column] or \
                          [None]
            results = []

            product_idx = columns.index('product')
            column_indices = range(len(columns))
            for row in cursor:
                result = {}
                for i in column_indices:
                    name, field, val = columns[i], fields[i], row[i]
                    if name == 'reporter':
                        val = val or 'anonymous'
                    elif name == 'id':
                        val = int(val)
                        if not isinstance(self.env, ProductEnvironment):
                            # global -> retrieve ProductizedHref()
                            result['href'] = self._get_ticket_href(
                                row[product_idx], val)
                        elif href is not None:
                            result['href'] = href.ticket(val)
                    elif name in self.time_fields:
                        val = from_utimestamp(val)
                    elif field and field['type'] == 'checkbox':
                        try:
                            val = bool(int(val))
                        except (TypeError, ValueError):
                            val = False
                    elif val is None:
                        val = ''
                    result[name] = val
                results.append(result)
            cursor.close()
            return results


class ProductQueryModule(QueryModule):
    def process_request(self, req):
        req.perm.assert_permission('TICKET_VIEW')

        constraints = self._get_constraints(req)
        args = req.args
        if not constraints and not 'order' in req.args:
            # If no constraints are given in the URL, use the default ones.
            if req.authname and req.authname != 'anonymous':
                qstring = self.default_query
                user = req.authname
            else:
                email = req.session.get('email')
                name = req.session.get('name')
                qstring = self.default_anonymous_query
                user = email or name or None

            self.log.debug('QueryModule: Using default query: %s', str(qstring))
            if qstring.startswith('?'):
                arg_list = parse_arg_list(qstring[1:])
                args = arg_list_to_args(arg_list)
                constraints = self._get_constraints(arg_list=arg_list)
            else:
                query = ProductQuery.from_string(self.env, qstring)
                args = {'order': query.order, 'group': query.group,
                        'col': query.cols, 'max': query.max}
                if query.desc:
                    args['desc'] = '1'
                if query.groupdesc:
                    args['groupdesc'] = '1'
                constraints = query.constraints

            # Substitute $USER, or ensure no field constraints that depend
            # on $USER are used if we have no username.
            for clause in constraints:
                for field, vals in clause.items():
                    for (i, val) in enumerate(vals):
                        if user:
                            vals[i] = val.replace('$USER', user)
                        elif val.endswith('$USER'):
                            del clause[field]
                            break

        cols = args.get('col')
        if isinstance(cols, basestring):
            cols = [cols]
        # Since we don't show 'id' as an option to the user,
        # we need to re-insert it here.
        if cols and 'id' not in cols:
            cols.insert(0, 'id')
        rows = args.get('row', [])
        if isinstance(rows, basestring):
            rows = [rows]
        format = req.args.get('format')
        max = args.get('max')
        if max is None and format in ('csv', 'tab'):
            max = 0 # unlimited unless specified explicitly
        query = ProductQuery(self.env, req.args.get('report'),
                      constraints, cols, args.get('order'),
                      'desc' in args, args.get('group'),
                      'groupdesc' in args, 'verbose' in args,
                      rows,
                      args.get('page'),
                      max)

        if 'update' in req.args:
            # Reset session vars
            for var in ('query_constraints', 'query_time', 'query_tickets'):
                if var in req.session:
                    del req.session[var]
            req.redirect(query.get_href(req.href))

        # Add registered converters
        for conversion in Mimeview(self.env).get_supported_conversions(
                                             'trac.ticket.Query'):
            add_link(req, 'alternate',
                     query.get_href(req.href, format=conversion[0]),
                     conversion[1], conversion[4], conversion[0])

        if format:
            filename = 'query' if format != 'rss' else None
            Mimeview(self.env).send_converted(req, 'trac.ticket.Query', query,
                                              format, filename=filename)

        return self.display_html(req, query)

    def display_html(self, req, query):
        # The most recent query is stored in the user session;
        orig_list = None
        orig_time = datetime.now(utc)
        query_time = int(req.session.get('query_time', 0))
        query_time = datetime.fromtimestamp(query_time, utc)
        query_constraints = unicode(query.constraints)
        try:
            if query_constraints != req.session.get('query_constraints') \
                    or query_time < orig_time - timedelta(hours=1):
                tickets = query.execute(req)
                # New or outdated query, (re-)initialize session vars
                req.session['query_constraints'] = query_constraints
                req.session['query_tickets'] = ' '.join([str(t['id'])
                                                         for t in tickets])
            else:
                orig_list = [int(id) for id
                             in req.session.get('query_tickets', '').split()]
                tickets = query.execute(req, cached_ids=orig_list)
                orig_time = query_time
        except QueryValueError, e:
            tickets = []
            for error in e.errors:
                add_warning(req, error)

        context = web_context(req, 'query')
        owner_field = [f for f in query.fields if f['name'] == 'owner']
        if owner_field:
            TicketSystem(self.env).eventually_restrict_owner(owner_field[0])
        data = query.template_data(context, tickets, orig_list, orig_time, req)

        req.session['query_href'] = query.get_href(context.href)
        req.session['query_time'] = to_timestamp(orig_time)
        req.session['query_tickets'] = ' '.join([str(t['id'])
                                                 for t in tickets])
        title = _('Custom Query')

        # Only interact with the report module if it is actually enabled.
        #
        # Note that with saved custom queries, there will be some convergence
        # between the report module and the query module.
        from trac.ticket.report import ReportModule
        if 'REPORT_VIEW' in req.perm and \
               self.env.is_component_enabled(ReportModule):
            data['report_href'] = req.href.report()
            add_ctxtnav(req, _('Available Reports'), req.href.report())
            add_ctxtnav(req, _('Custom Query'), req.href.query())
            if query.id:
                for title, description in self.env.db_query("""
                        SELECT title, description FROM report WHERE id=%s
                        """, (query.id,)):
                    data['report_resource'] = Resource('report', query.id)
                    data['description'] = description
        else:
            data['report_href'] = None

        # Only interact with the batch modify module it it is enabled
        # TODO: fix this for multiproduct
        """
        from trac.ticket.batch import BatchModifyModule
        if 'TICKET_BATCH_MODIFY' in req.perm and \
                self.env.is_component_enabled(BatchModifyModule):
            self.env[BatchModifyModule].add_template_data(req, data, tickets)
        """

        data.setdefault('report', None)
        data.setdefault('description', None)
        data['title'] = title

        data['all_columns'] = query.get_all_columns()
        # Don't allow the user to remove the id column
        data['all_columns'].remove('id')
        data['all_textareas'] = query.get_all_textareas()

        properties = dict((name, dict((key, field[key])
                                      for key in ('type', 'label', 'options',
                                                  'optgroups')
                                      if key in field))
                          for name, field in data['fields'].iteritems())
        add_script_data(req, properties=properties, modes=data['modes'])

        add_stylesheet(req, 'common/css/report.css')
        Chrome(self.env).add_jquery_ui(req)
        add_script(req, 'common/js/query.js')

        return 'query.html', data, None


class ProductTicketQueryMacro(TicketQueryMacro):
    """TracQuery macro retrieving results across product boundaries. 
    """
    def expand_macro(self, formatter, name, content):
        req = formatter.req
        query_string, kwargs, format = self.parse_args(content)
        if query_string:
            query_string += '&'
        query_string += '&'.join('%s=%s' % item
                                 for item in kwargs.iteritems())
        query = ProductQuery.from_string(self.env, query_string)

        if format == 'count':
            cnt = query.count(req)
            return tag.span(cnt, title='%d tickets for which %s' %
                            (cnt, query_string), class_='query_count')

        tickets = query.execute(req)

        if format == 'table':
            data = query.template_data(formatter.context, tickets,
                                       req=formatter.context.req)

            add_stylesheet(req, 'common/css/report.css')

            return Chrome(self.env).render_template(
                req, 'query_results.html', data, None, fragment=True)

        if format == 'progress':
            from trac.ticket.roadmap import (RoadmapModule,
                                             apply_ticket_permissions,
                                             get_ticket_stats,
                                             grouped_stats_data)

            add_stylesheet(req, 'common/css/roadmap.css')

            def query_href(extra_args, group_value = None):
                q = Query.from_string(self.env, query_string)
                if q.group:
                    extra_args[q.group] = group_value
                    q.group = None
                for constraint in q.constraints:
                    constraint.update(extra_args)
                if not q.constraints:
                    q.constraints.append(extra_args)
                return q.get_href(formatter.context)
            chrome = Chrome(self.env)
            tickets = apply_ticket_permissions(self.env, req, tickets)
            stats_provider = RoadmapModule(self.env).stats_provider
            by = query.group
            if not by:
                stat = get_ticket_stats(stats_provider, tickets)
                data = {
                    'stats': stat,
                    'stats_href': query_href(stat.qry_args),
                    'interval_hrefs': [query_href(interval['qry_args'])
                                       for interval in stat.intervals],
                    'legend': True,
                }
                return tag.div(
                    chrome.render_template(req, 'progress_bar.html', data,
                                           None, fragment=True),
                    class_='trac-progress')

            def per_group_stats_data(gstat, group_name):
                return {
                    'stats': gstat,
                    'stats_href': query_href(gstat.qry_args,  group_name),
                    'interval_hrefs': [query_href(interval['qry_args'],
                                                  group_name)
                                       for interval in gstat.intervals],
                    'percent': '%d / %d' % (gstat.done_count,
                                            gstat.count),
                    'legend': False,
                }

            groups = grouped_stats_data(self.env, stats_provider, tickets, by,
                                        per_group_stats_data)
            data = {
                'groups': groups, 'grouped_by': by,
                'summary': _("Ticket completion status for each %(group)s",
                             group=by),
            }
            return tag.div(
                chrome.render_template(req, 'progress_bar_grouped.html', data,
                                       None, fragment=True),
                class_='trac-groupprogress')

        # Formats above had their own permission checks, here we need to
        # do it explicitly:

        tickets = [t for t in tickets
                   if 'TICKET_VIEW' in req.perm('ticket', t['id'])]

        if not tickets:
            return tag.span(_("No results"), class_='query_no_results')

        # Cache resolved href targets
        hrefcache = {}

        def ticket_anchor(ticket):
            try:
                pvalue = ticket.get('product') or GLOBAL_PRODUCT
                envhref = hrefcache[pvalue]
            except KeyError:
                try:
                    env = lookup_product_env(self.env, prefix= pvalue,
                                             name=pvalue)
                except LookupError:
                    return tag.a('#%s' % ticket['id'], 
                                 class_='missing product')
                hrefcache[pvalue] = envhref = resolve_product_href(
                         to_env=env, at_env=self.env)
            return tag.a('#%s' % ticket['id'],
                         class_=ticket['status'],
                         href=envhref.ticket(int(ticket['id'])),
                         title=shorten_line(ticket['summary']))

        def ticket_groups():
            groups = []
            for v, g in groupby(tickets, lambda t: t[query.group]):
                q = Query.from_string(self.env, query_string)
                # produce the hint for the group
                q.group = q.groupdesc = None
                order = q.order
                q.order = None
                title = _("%(groupvalue)s %(groupname)s tickets matching "
                          "%(query)s", groupvalue=v, groupname=query.group,
                          query=q.to_string())
                # produce the href for the query corresponding to the group
                for constraint in q.constraints:
                    constraint[str(query.group)] = v
                q.order = order
                href = q.get_href(formatter.context)
                groups.append((v, [t for t in g], href, title))
            return groups

        if format == 'compact':
            if query.group:
                groups = [(v, ' ',
                           tag.a('#%s' % u',\u200b'.join(str(t['id'])
                                                         for t in g),
                                 href=href, class_='query', title=title))
                          for v, g, href, title in ticket_groups()]
                return tag(groups[0], [(', ', g) for g in groups[1:]])
            else:
                alist = [ticket_anchor(ticket) for ticket in tickets]
                return tag.span(alist[0], *[(', ', a) for a in alist[1:]])
        else:
            if query.group:
                return tag.div(
                    [(tag.p(tag_('%(groupvalue)s %(groupname)s tickets:',
                                 groupvalue=tag.a(v, href=href, class_='query',
                                                  title=title),
                                 groupname=query.group)),
                      tag.dl([(tag.dt(ticket_anchor(t)),
                               tag.dd(t['summary'])) for t in g],
                             class_='wiki compact'))
                     for v, g, href, title in ticket_groups()])
            else:
                return tag.div(tag.dl([(tag.dt(ticket_anchor(ticket)),
                                        tag.dd(ticket['summary']))
                                       for ticket in tickets],
                                      class_='wiki compact'))

    def is_inline(self, content):
        query_string, kwargs, format = self.parse_args(content)
        return format in ('count', 'compact')
