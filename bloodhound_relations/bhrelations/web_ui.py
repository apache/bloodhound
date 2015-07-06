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

from trac.core import Component, TracError, implements
from trac.resource import Resource, get_resource_shortname, \
                          get_resource_summary, get_resource_url
from trac.ticket.model import Ticket
from trac.util import exception_to_unicode, to_unicode
from trac.web.api import IRequestFilter, IRequestHandler
from trac.web.chrome import ITemplateProvider, add_warning

from bhrelations.api import NoSuchTicketError, RelationsSystem, \
                            ResourceIdSerializer, TicketRelationsSpecifics, \
                            UnknownRelationType

from bhrelations.model import Relation
from bhrelations.utils.translation import _
from bhrelations.validation import ValidationError


class RelationManagementModule(Component):
    implements(IRequestFilter, IRequestHandler, ITemplateProvider)

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

        # For access to the relation management, TICKET_MODIFY is required.
        req.perm.require('TICKET_MODIFY')
        relsys = RelationsSystem(self.env)

        data = {
            'relation': {},
        }
        if req.method == 'POST':
            # for modifying the relations TICKET_MODIFY is required for
            # both the source and the destination tickets

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
                    trs = TicketRelationsSpecifics(self.env)
                    dest_ticket = trs.find_ticket(relation['destination'])
                except NoSuchTicketError:
                    data['error'] = _('Invalid ticket ID.')
                else:
                    req.perm.require('TICKET_MODIFY', Resource(dest_ticket.id))

                    try:
                        dbrel = relsys.add(ticket, dest_ticket,
                                           relation['type'],
                                           relation['comment'], req.authname)
                    except NoSuchTicketError:
                        data['error'] = _('Invalid ticket ID.')
                    except UnknownRelationType:
                        data['error'] = _('Unknown relation type.')
                    except ValidationError as ex:
                        data['error'] = ex.message
                    else:
                        # Notify
                        try:
                            self.notify_relation_changed(dbrel)
                        except Exception, e:
                            self.log.error("Failure sending notification on"
                                           "creation of relation: %s",
                                           exception_to_unicode(e))
                            add_warning(req, _("The relation has been added, "
                                               "but an error occurred while "
                                               "sending notifications: "
                                               "%(message)s",
                                               message=to_unicode(e)))

                if 'error' in data:
                    data['relation'] = relation
            else:
                raise TracError(_('Invalid operation.'))

        data.update({
            'ticket': ticket,
            'reltypes': sorted(relsys.get_relation_types().iteritems(),
                               key=lambda x: x[0]),
            'relations': self.get_ticket_relations(ticket),
            'get_resource_shortname': get_resource_shortname,
            'get_resource_summary': get_resource_summary,
        })
        return 'relations_manage.html', data, None

    def notify_relation_changed(self, relation):
        from bhrelations.notification import RelationNotifyEmail
        RelationNotifyEmail(self.env).notify(relation)

    # ITemplateProvider methods

    def get_htdocs_dirs(self):
        return []

    def get_templates_dirs(self):
        from pkg_resources import resource_filename
        return [resource_filename('bhrelations', 'templates')]

    # IRequestFilter methods

    def pre_process_request(self, req, handler):
        return handler

    def post_process_request(self, req, template, data, content_type):
        if req.path_info.startswith('/ticket/'):
            ticket = data['ticket']
            rls = RelationsSystem(self.env)
            try:
                resid = ResourceIdSerializer \
                            .get_resource_id_from_instance(self.env, ticket)
            except ValueError:
                resid = None

            if rls.duplicate_relation_type and resid is not None:
                duplicate_relations = \
                    rls._select_relations(resid, rls.duplicate_relation_type)
                if duplicate_relations:
                    data['ticket_duplicate_of'] = \
                        duplicate_relations[0].destination
        return template, data, content_type

    # Public methods

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

    def remove_relations(self, req, rellist):
        relsys = RelationsSystem(self.env)
        for relid in rellist:
            relation = Relation.load_by_relation_id(self.env, relid)
            resource = \
                ResourceIdSerializer.get_resource_by_id(relation.destination)
            if 'TICKET_MODIFY' in req.perm(resource):
                relsys.delete(relid)
            else:
                add_warning(req, _('Insufficient permissions to remove '
                                   'relation "%(relation)s"', relation=relid))
