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
from trac.notification import NotifyEmail
from trac.ticket.notification import (get_ticket_notification_recipients,
                                      TicketNotifyEmail)
from trac.util.datefmt import from_utimestamp
from trac.web.chrome import Chrome

from bhrelations.api import ResourceIdSerializer, TicketRelationsSpecifics


class RelationNotifyEmail(TicketNotifyEmail):
    template_name = "relation_notify_email.txt"

    imitate_ticket_notification = False

    def notify(self, relation, deleted=False):
        self.relation = relation
        source = ResourceIdSerializer.get_resource_by_id(relation.source)
        if source.realm == 'ticket':
            self.imitate_ticket_notification = True
            helper = TicketRelationsSpecifics(self.env)
            t = helper._create_ticket_by_full_id(source)
            self.template = Chrome(self.env).load_template(
                TicketNotifyEmail.template_name, method='text')
            if deleted:
                modtime = deleted
            else:
                modtime = from_utimestamp(relation.time)
            TicketNotifyEmail.notify(self, t, newticket=False, modtime=modtime)
        else:
            self._generic_notify(relation, deleted)

    def _generic_notify(self, relation, deleted):
        self.data.update(dict(
            created=not deleted,
            relation=relation,
        ))
        NotifyEmail.notify(self, '', '', '')

    def send(self, torcpts, ccrcpts):
        if self.imitate_ticket_notification:
            TicketNotifyEmail.send(self, torcpts, ccrcpts)
        else:
            NotifyEmail.send(self, torcpts, ccrcpts)

    def get_recipients(self, relid):
        relation = self.relation
        source, destination = map(ResourceIdSerializer.get_resource_by_id,
                                  (relation.source, relation.destination))
        to, cc = [], []
        for resource in (source, destination):
            if resource.realm == 'ticket':
                (torecipients, ccrecipients, reporter, owner) = \
                    get_ticket_notification_recipients(self.env, self.config,
                    resource.id, [])
                to.extend(torecipients)
                cc.extend(ccrecipients)
        return to, cc
