
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
from trac.ticket.web_ui import TicketModule
from trac.attachment import AttachmentModule
from trac.ticket.api import TicketSystem
from trac.resource import Resource, get_resource_shortname
from trac.search import search_to_sql, shorten_result
from trac.util.datefmt import from_utimestamp
from trac.util.translation import _, tag_
from genshi.builder import tag

from multiproduct.model import Product

PRODUCT_RE = re.compile(r'^/(?P<pid>[^/]*)(?P<pathinfo>.*)')
TICKET_RE = re.compile(r'/ticket/(?P<ticket>[0-9]+)$')
class ProductTicketModule(TicketModule):
    """Product Overrides for the TicketModule"""
    
    # IRequestHandler methods
    def match_request(self, req):
        """Override of TicketModule match_request"""
        match = PRODUCT_RE.match(req.path_info)
        if match:
            pid = match.group('pid')
            products = Product.select(self.env, where={'prefix':pid})
            if len(products) == 1:
                req.args['productid'] = match.group('pid')
                req.args['product'] = products[0].name
                pathinfo = match.group('pathinfo')
                # is it a newticket request:
                if pathinfo == "/newticket":
                    return True
                tmatch = TICKET_RE.match(pathinfo)
                if tmatch:
                    req.args['id'] = tmatch.group('ticket')
                    return True
    
    def process_request(self, req):
        """Override for TicketModule process_request"""
        if 'id' in req.args:
            if req.path_info == '/' + req.args['product'] + '/newticket':
                raise TracError(_("id can't be set for a new ticket request"))
            return self._process_ticket_request(req)
            #switch to the surrogate key
        return self._process_newticket_request(req)
    
    # INavigationContributor methods
    
    #def get_active_navigation_item(self, req):
    # override not yet required

    def get_navigation_items(self, req):
        """Overriding TicketModules New Ticket nav item"""
        if 'TICKET_CREATE' in req.perm:
            product = req.args.get('productid','')
            if product:
                href = req.href.__getattr__(product)('newticket')
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
