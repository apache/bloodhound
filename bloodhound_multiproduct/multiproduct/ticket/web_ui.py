
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
from genshi.builder import tag

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
        ticket = Ticket(self.env, ticketid)
        
        if ticketid:
            if (req.path_info == '/products/' + productid + '/newticket' or
                req.path_info == '/products'):
                raise TracError(_("id can't be set for a new ticket request."))
            ticket = Ticket(self.env, ticketid)
            if productid and ticket['product'] != req.args.get('product',''):
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
        if 'TICKET_CREATE' in req.perm:
            product = req.args.get('productid','')
            if product and self.env.is_component_enabled(ProductModule):
                # this path will only exist if ProductModule is active
                href = req.href('products', product, 'newticket')
            else:
                href = req.href.newticket()
            yield ('mainnav', 'newticket', 
                   tag.a(_("New Ticket"), href=href, accesskey=7))
    
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
    """replacement for ReportModule"""
    
    # IRequestHandler methods
    def match_request(self, req):
        """Override of ReportModule match_request"""
        pathinfo = match_product_path(self.env, req)
        match = REPORT_RE.match(pathinfo)
        if match:
            if match.group(1):
                req.args['id'] = match.group(1)
            return True
    
    #def process_request(self, req):
    # not yet required
