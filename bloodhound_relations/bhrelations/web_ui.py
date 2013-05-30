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
from trac.resource import get_resource_url, ResourceNotFound, Resource
from trac.ticket.model import Ticket
from trac.util.translation import _
from trac.web import IRequestHandler
from trac.web.chrome import ITemplateProvider, add_warning

from bhrelations.api import RelationsSystem, ResourceIdSerializer, \
    TicketRelationsSpecifics, UnknownRelationType
from bhrelations.model import Relation
from bhrelations.validation import ValidationError

from multiproduct.model import Product
from multiproduct.env import ProductEnvironment

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
            raise TracError(_('No ticket id provided.'))

        try:
            ticket = Ticket(self.env, tid)
        except ValueError:
            raise TracError(_('Invalid ticket id.'))

        req.perm.require('TICKET_VIEW')
        relsys = RelationsSystem(self.env)

        data = {
            'relation': {},
        }
        if req.method == 'POST':
            # for modifying the relations TICKET_MODIFY is required for
            # both the source and the destination tickets
            req.perm.require('TICKET_MODIFY')

            if 'remove' in req.args:
                rellist = req.args.get('sel')
                if rellist:
                    if isinstance(rellist, basestring):
                        rellist = [rellist, ]
                    self.remove_relations(req, rellist)
            elif 'add' in req.args:
                relation = dict(
                    destination=req.args.get('dest_tid', ''),
                    type=req.args.get('reltype', ''),
                    comment=req.args.get('comment', ''),
                )
                try:
                    dest_ticket = self.find_ticket(relation['destination'])
                    req.perm.require('TICKET_MODIFY',
                                     Resource(dest_ticket.id))
                    relsys.add(ticket, dest_ticket,
                               relation['type'],
                               relation['comment'],
                               req.authname)
                except NoSuchTicketError:
                    data['error'] = _('Invalid ticket id.')
                except UnknownRelationType:
                    data['error'] = _('Unknown relation type.')
                except ValidationError as ex:
                    data['error'] = ex.message
                if 'error' in data:
                    data['relation'] = relation

            else:
                raise TracError(_('Invalid operation.'))

        data.update({
            'ticket': ticket,
            'reltypes': relsys.get_relation_types(),
            'relations': self.get_ticket_relations(ticket),
        })
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
        reltypes = relsys.get_relation_types()
        trs = TicketRelationsSpecifics(self.env)
        for r in relsys.get_relations(ticket):
            r['desthref'] = get_resource_url(self.env, r['destination'],
                self.env.href)
            r['destticket'] = trs._create_ticket_by_full_id(r['destination'])
            grouped_relations.setdefault(reltypes[r['type']], []).append(r)
        return grouped_relations

    def find_ticket(self, ticket_spec):
        ticket = None
        m = re.match(r'#?(?P<tid>\d+)', ticket_spec)
        if m:
            tid = m.group('tid')
            try:
                ticket = Ticket(self.env, tid)
            except ResourceNotFound:
                # ticket not found in current product, try all other products
                for p in Product.select(self.env):
                    if p.prefix != self.env.product.prefix:
                        # TODO: check for PRODUCT_VIEW permissions
                        penv = ProductEnvironment(self.env.parent, p.prefix)
                        try:
                            ticket = Ticket(penv, tid)
                        except ResourceNotFound:
                            pass
                        else:
                            break

        # ticket still not found, use fallback for <prefix>:ticket:<id> syntax
        if ticket is None:
            trs = TicketRelationsSpecifics(self.env)
            try:
                resource = ResourceIdSerializer.get_resource_by_id(tid)
                ticket = trs._create_ticket_by_full_id(resource)
            except:
                raise NoSuchTicketError
        return ticket

    def remove_relations(self, req, rellist):
        relsys = RelationsSystem(self.env)
        for relid in rellist:
            relation = Relation.load_by_relation_id(self.env, relid)
            resource = ResourceIdSerializer.get_resource_by_id(
                relation.destination)
            if 'TICKET_MODIFY' in req.perm(resource):
                relsys.delete(relid)
            else:
                add_warning(req,
                    _('Not enough permissions to remove relation "%s"' % relid))


class NoSuchTicketError(ValueError):
    pass
