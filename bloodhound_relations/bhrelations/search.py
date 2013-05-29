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

from sqlite3 import OperationalError

from trac.core import Component, implements

from bhsearch.api import IDocIndexPreprocessor
from bhsearch.search_resources.ticket_search import TicketIndexer

from bhrelations.api import RelationsSystem, ResourceIdSerializer,\
    IRelationChangingListener, TicketRelationsSpecifics


class RelationsDocPreprocessor(Component):
    implements(IDocIndexPreprocessor)

    def pre_process(self, doc):
        resource_id = ':'.join([
            doc.get('product', ''), doc.get('type', ''), doc.get('id')])

        try:
            rls = RelationsSystem(self.env)
            relations = []
            for relation in rls._select_relations(resource_id):
                relations.extend(self._format_relations(relation))
            doc['relations'] = ','.join(relations)
        except OperationalError:
            # If bhrelations and bhsearch are installed at the same time and
            # bhsearch is upgraded before bhrelations, table
            # bloodhound_relations will be missing, thus causing the
            # OperationalError. As this means that the relations do not
            # exist yet, just skip indexing them.
            self.log.debug("Not indexing relations for %s", resource_id)

    def _format_relations(self, relation):
        ris = ResourceIdSerializer
        product, realm, res_id = ris.split_full_id(relation.destination)

        if realm == 'ticket':
            yield '%s:#%s' % (relation.type, res_id)
            yield '%s:#%s-%s' % (relation.type, product, res_id)
        elif realm == 'wiki':
            yield '%s:%s' % (relation.type, res_id)


class RelationSearchUpdater(Component):
    implements(IRelationChangingListener)

    def adding_relation(self, relation):
        self._reindex_endpoints(relation)

    def deleting_relation(self, relation, when):
        self._reindex_endpoints(relation)

    def _reindex_endpoints(self, relation):
        trs = TicketRelationsSpecifics(self.env)
        ticket_indexer = TicketIndexer(self.env)
        for resource in map(ResourceIdSerializer.get_resource_by_id,
                            (relation.source, relation.destination)):
            if resource.realm == 'ticket':
                ticket = trs._create_ticket_by_full_id(resource)
                ticket_indexer._index_ticket(ticket)
