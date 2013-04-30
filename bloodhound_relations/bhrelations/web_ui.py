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


r"""Ticket relations for Apache(TM) Bloodhound

Ticket relations user interface.
"""

import re
import pkg_resources

from trac.core import Component, implements, TracError
from trac.resource import get_resource_url
from trac.ticket.model import Ticket
from trac.web import IRequestHandler
from trac.web.chrome import ITemplateProvider

from bhrelations.api import RelationsSystem


class RelationManagementModule(Component):
    implements(IRequestHandler, ITemplateProvider)

    # IRequestHandler methods
    def match_request(self, req):
        match = re.match(r'/ticket/([0-9]+)/relations/*$', req.path_info)
        if not match:
            return False

        req.args['id'] = match.group(1)
        return True

    def process_request(self, req):
        tid = req.args.get('id')
        if not tid:
            raise TracError('No ticket id provided.')

        req.perm.require('TICKET_VIEW')
        ticket = Ticket(self.env, tid)
        data = {
            'ticket': ticket,
            'relations': self.get_ticket_relations(ticket),
        }
        return 'manage.html', data, None

    # ITemplateProvider methods
    def get_htdocs_dirs(self):
        resource_filename = pkg_resources.resource_filename
        return [resource_filename('bhrelations', 'htdocs'), ]

    def get_templates_dirs(self):
        resource_filename = pkg_resources.resource_filename
        return [resource_filename('bhrelations', 'templates'), ]

    # utility functions
    def get_ticket_relations(self, ticket):
        grouped_relations = {}
        for r in RelationsSystem(self.env).get_relations(ticket):
            r['desthref'] = get_resource_url(self.env, r['destination'],
                self.env.href)
            grouped_relations.setdefault(r['type'], []).append(r)
        return grouped_relations

