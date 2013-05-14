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
        relsys = RelationsSystem(self.env)

        if req.method == 'POST':
            if req.args.has_key('remove'):
                rellist = req.args.get('sel')
                if rellist:
                    if isinstance(rellist, basestring):
                        rellist = [rellist, ]
                    for rel in rellist:
                        relsys.delete(rel)
            elif req.args.has_key('add'):
                dest_tid = req.args.get('dest_tid')
                reltype = req.args.get('reltype')
                comment = req.args.get('comment')
                if dest_tid and reltype:
                    dest_ticket = Ticket(self.env, dest_tid)
                    relsys.add(ticket, dest_ticket, reltype, comment,
                        req.authname)
            else:
                raise TracError(_('Invalid operation.'))

        data = {
            'ticket': ticket,
            'reltypes': relsys.get_relation_types(),
            'relations': self.get_ticket_relations(ticket),
        }
        return 'manage.html', data, None

    # ITemplateProvider methods
    def get_htdocs_dirs(self):
        resource_filename = pkg_resources.resource_filename
        return [('relations', resource_filename('bhrelations', 'htdocs')), ]

    def get_templates_dirs(self):
        resource_filename = pkg_resources.resource_filename
        return [resource_filename('bhrelations', 'templates'), ]

    # utility functions
    def get_ticket_relations(self, ticket):
        grouped_relations = {}
        relsys = RelationsSystem(self.env)
        for r in relsys.get_relations(ticket):
            r['desthref'] = get_resource_url(self.env, r['destination'],
                self.env.href)
            r['label'] = relsys.render_relation_type(r['type'])
            grouped_relations.setdefault(r['type'], []).append(r)
        return grouped_relations

