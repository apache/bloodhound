
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

""" Multi product support for tickets."""

import re

from genshi.builder import tag

from trac.core import TracError
from trac.ticket.model import Ticket
from trac.ticket.web_ui import TicketModule
from trac.ticket.report import ReportModule
from trac.attachment import AttachmentModule
from trac.ticket.api import TicketSystem
from trac.resource import Resource, get_resource_shortname, ResourceNotFound
from trac.search import search_to_sql, shorten_result
from trac.util.datefmt import from_utimestamp
from trac.util.translation import _, tag_
from trac.wiki.parser import WikiParser

from multiproduct.api import MultiProductSystem, PRODUCT_SYNTAX_DELIMITER_RE
from multiproduct.env import lookup_product_env, ProductEnvironment
from multiproduct.util import IDENTIFIER
from multiproduct.web_ui import ProductModule

REPORT_RE = re.compile(r'/report(?:/(?:([0-9]+)|-1))?$')

class ProductTicketModule(TicketModule):
    """Product Overrides for the TicketModule"""
    
    # IRequestHandler methods
    #def match_request(self, req):
    # override not yet required
    
    def process_request(self, req):
        """Override for TicketModule process_request"""
        ticketid = req.args.get('id')
        productid = req.args.get('productid','')
        
        if ticketid:
            if req.path_info in ('/newticket', '/products'):
                raise TracError(_("id can't be set for a new ticket request."))
            ticket = Ticket(self.env, ticketid)
            if productid and ticket['product'] != productid:
                msg = "Ticket %(id)s in product '%(prod)' does not exist."
                raise ResourceNotFound(_(msg, id=ticketid, prod=productid),
                                       _("Invalid ticket number"))
            return self._process_ticket_request(req)
        return self._process_newticket_request(req)
    
    # INavigationContributor methods
    
    #def get_active_navigation_item(self, req):
    # override not yet required

    def get_navigation_items(self, req):
        """Overriding TicketModules New Ticket nav item"""
        return
    
    # ISearchSource methods
    #def get_search_filters(self, req):
    # override not yet required
    
    def get_search_results(self, req, terms, filters):
        """Overriding search results for Tickets"""
        if not 'ticket' in filters:
            return
        ticket_realm = Resource('ticket')
        with self.env.db_query as db:
            sql, args = search_to_sql(db, ['summary', 'keywords',
                                           'description', 'reporter', 'cc', 
                                           db.cast('id', 'text')], terms)
            sql2, args2 = search_to_sql(db, ['newvalue'], terms)
            sql3, args3 = search_to_sql(db, ['value'], terms)
            ticketsystem = TicketSystem(self.env)
            if req.args.get('product'):
                productsql = "product='%s' AND" % req.args.get('product')
            else:
                productsql = ""
            
            for summary, desc, author, type, tid, ts, status, resolution in \
                    db("""SELECT summary, description, reporter, type, id,
                                 time, status, resolution 
                          FROM ticket
                          WHERE (%s id IN (
                              SELECT id FROM ticket WHERE %s
                            UNION
                              SELECT ticket FROM ticket_change
                              WHERE field='comment' AND %s
                            UNION
                              SELECT ticket FROM ticket_custom WHERE %s
                          ))
                          """ % (productsql, sql, sql2, sql3),
                          args + args2 + args3):
                t = ticket_realm(id=tid)
                if 'TICKET_VIEW' in req.perm(t):
                    yield (req.href.ticket(tid),
                           tag_("%(title)s: %(message)s",
                                title=tag.span(
                                    get_resource_shortname(self.env, t),
                                    class_=status),
                                message=ticketsystem.format_summary(
                                    summary, status, resolution, type)),
                           from_utimestamp(ts), author,
                           shorten_result(desc, terms))
        
        # Attachments
        for result in AttachmentModule(self.env).get_search_results(
            req, ticket_realm, terms):
            yield result

class ProductReportModule(ReportModule):
    """Multiproduct replacement for ReportModule"""

    # INavigationContributor methods
    #def get_active_navigation_item(self, req):
    # not yet required

    def get_navigation_items(self, req):
        if 'REPORT_VIEW' in req.perm:
            href = ProductModule.get_product_path(self.env, req, 'report')
            yield ('mainnav', 'tickets', tag.a(_('View Tickets'), href=href))

    # IWikiSyntaxProvider methods
    #def get_link_resolvers(self):
    # not yet required

    def get_wiki_syntax(self):
        # FIXME: yield from
        for s in super(ProductReportModule, self).get_wiki_syntax():
            yield s
        # Previously unmatched prefix 
        yield (r"!?\{(?P<prp>%s(?:\s+|(?:%s)))[0-9]+\}" % 
                    (IDENTIFIER, PRODUCT_SYNTAX_DELIMITER_RE),
               lambda x, y, z: self._format_link(x, 'report', y[1:-1], y, z))
        # Absolute product report syntax
        yield (r"!?\{(?P<prns>global:|product:%s(?:\s+|:))"
               r"(?P<prid>[0-9]+)\}" % (IDENTIFIER,),
               lambda x, y, z: (self._format_mplink(x, 'report', y[1:-1], y, z)))

    def _format_link(self, formatter, ns, target, label, fullmatch=None):
        intertrac = formatter.shorthand_intertrac_helper(ns, target, label,
                                                         fullmatch)
        if intertrac:
            return intertrac

        # second chance to match InterTrac prefix as product prefix
        it_report = fullmatch.group('it_' + ns) or fullmatch.group('prp')
        if it_report:
            return self._format_mplink(formatter, ns, target, label, fullmatch)

        report, args, fragment = formatter.split_link(target)
        return tag.a(label, href=formatter.href.report(report) + args,
                     class_='report')

    def _format_mplink(self, formatter, ns, target, label, fullmatch=None):
        mpsys = self.env[MultiProductSystem]
        if mpsys is not None:
            substeps = []
            prns = fullmatch.group('prns')
            if not prns:
                # Forwarded from _format_link, inherit current context
                product_id = fullmatch.group('it_' + ns) or \
                             fullmatch.group('prp') 
                if product_id:
                    product_ns = 'product'
                    substeps = [product_id.strip()]
                elif isinstance(self.env, ProductEnvironment):
                    product_ns = 'product'
                    substeps = [self.env.product.prefix]
                else:
                    product_ns = 'global'
            elif prns == 'global:':
                product_ns = 'global'
            elif prns.startswith('product:'):
                product_ns, product_id = prns.strip().split(':')[:2]
                substeps = [product_id]
            report_id = fullmatch.group('prid') or \
                        re.match(r'^.*?(\d+)$', target).group(1)
            substeps += [ns, report_id]
            
            return mpsys._format_link(formatter, product_ns, 
                                      u':'.join(substeps),
                                      label, fullmatch)
        else:
            return tag.a(label, class_='missing product')
