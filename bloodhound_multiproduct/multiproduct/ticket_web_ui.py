
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

""" Multi product support for tickets """

import re

from trac.core import TracError
from trac.ticket.web_ui import TicketModule
from trac.util.translation import _
from genshi.builder import tag

from model import Product

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
            if Product.select(self.env, where={'prefix':pid}):
                req.args['product'] = match.group('pid')
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
    # override not required

    def get_navigation_items(self, req):
        """Overriding TicketModules New Ticket nav item"""
        if 'TICKET_CREATE' in req.perm:
            product = req.args.get('product','')
            if product:
                href = req.href.__getattr__(product)('newticket')
            else:
                href = req.href.newticket()
            yield ('mainnav', 'newticket', 
                   tag.a(_("New Ticket"), href=href, accesskey=7))
