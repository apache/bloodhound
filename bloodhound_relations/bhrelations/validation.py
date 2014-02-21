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

from trac.core import Component, implements, TracError
from trac.resource import get_resource_shortname

from bhrelations.api import IRelationValidator, RelationsSystem, \
    ResourceIdSerializer, TicketRelationsSpecifics


class Validator(Component):
    implements(IRelationValidator)

    def validate(self, relation):
        raise NotImplementedError

    def render_relation_type(self, end):
        return RelationsSystem(self.env)._labels[end]

    def get_resource_name(self, resource_id):
        resource = ResourceIdSerializer.get_resource_by_id(resource_id)
        return get_resource_shortname(self.env, resource)

    def _find_path(self, source, destination, relation_type):
        known_nodes, paths = self._bfs(source, destination, relation_type)
        return paths.get((source, destination), None)

    def _descendants(self, source, relation_type):
        known_nodes, paths = self._bfs(source, None, relation_type)
        return known_nodes - set([source])

    def _ancestors(self, source, relation_type):
        known_nodes, paths = self._bfs(source, None, relation_type,
                                       reverse=True)
        return known_nodes - set([source])

    def _bfs(self, source, destination, relation_type, reverse=False):
        known_nodes = set([source])
        new_nodes = set([source])
        paths = {(source, source): [source]}

        while new_nodes:
            if reverse:
                relation = 'source, destination'
                origin = 'source'
            else:
                relation = 'destination, source'
                origin = 'destination'
            relation_types = \
                ','.join("'%s'" % r for r in relation_type.split(','))
            query = """
                SELECT %(relation)s
                  FROM bloodhound_relations
                 WHERE type IN (%(relation_type)s)
                   AND %(origin)s IN (%(new_nodes)s)
            """ % dict(
                relation=relation,
                relation_type=relation_types,
                new_nodes=', '.join("'%s'" % n for n in new_nodes),
                origin=origin)
            new_nodes = set()
            for s, d in self.env.db_query(query):
                if d not in known_nodes:
                    new_nodes.add(d)
                paths[(source, d)] = paths[(source, s)] + [d]
            known_nodes = set.union(known_nodes, new_nodes)
            if destination in new_nodes:
                break
        return known_nodes, paths


class NoCyclesValidator(Validator):
    def validate(self, relation):
        """If a path exists from relation's destination to its source,
         adding the relation will create a cycle.
         """
        path = self._find_path(relation.source,
                               relation.destination,
                               relation.type)
        if path:
            cycle_str = map(self.get_resource_name, path)
            error = 'Cycle in ''%s'': %s' % (
                self.render_relation_type(relation.type),
                ' -> '.join(cycle_str))
            error = ValidationError(error)
            error.failed_ids = path
            raise error


class ExclusiveValidator(Validator):
    def validate(self, relation):
        """If a path of exclusive type exists between source and destination,
        adding a relation is not allowed.
        """
        rls = RelationsSystem(self.env)
        source, destination = relation.source, relation.destination

        for exclusive_type in rls._exclusive:
            path = (self._find_path(source, destination, exclusive_type)
                    or self._find_path(destination, source, exclusive_type))
            if path:
                raise ValidationError(
                    "Cannot add relation %s, source and destination "
                    "are connected with %s relation." % (
                        self.render_relation_type(relation.type),
                        self.render_relation_type(exclusive_type),
                    )
                )
        if relation.type in rls._exclusive:
            d_ancestors = self._ancestors(destination, exclusive_type)
            d_ancestors.add(destination)
            s_descendants = self._descendants(source, exclusive_type)
            s_descendants.add(source)
            query = """
                SELECT source, destination, type
                  FROM bloodhound_relations
                 WHERE (source in (%(s_ancestors)s)
                        AND destination in (%(d_descendants)s))
                    OR
                       (source in (%(d_descendants)s)
                        AND destination in (%(s_ancestors)s))
            """ % dict(
                s_ancestors=', '.join("'%s'" % n for n in d_ancestors),
                d_descendants=', '.join("'%s'" % n for n in s_descendants))
            conflicting_relations = list(self.env.db_query(query))
            if conflicting_relations:
                raise ValidationError(
                    "Connecting %s and %s with relation %s "
                    "would make the following relations invalid:\n"
                    "%s" % (
                        source,
                        destination,
                        self.render_relation_type(relation.type),
                        '\n'.join(map(str, conflicting_relations))
                    )
                )


class SingleProductValidator(Validator):
    def validate(self, relation):
        product1, product2 = map(self.get_product,
                                 (relation.source, relation.destination))
        if product1 != product2:
            raise ValidationError(
                "Resources for %s relation must belong to the same product." %
                self.render_relation_type(relation.type)
            )

    def get_product(self, resource_id):
        return ResourceIdSerializer.split_full_id(resource_id)[0]


class NoSelfReferenceValidator(Validator):
    def validate(self, relation):
        if relation.source == relation.destination:
            error = ValidationError(
                'Ticket cannot be self-referenced in a relation.')
            error.failed_ids = [relation.source]
            raise error


class OneToManyValidator(Validator):
    def validate(self, relation):
        rls = RelationsSystem(self.env)
        existing_relations = rls._select_relations(relation.source,
                                                   relation.type)
        if existing_relations:
            raise ValidationError(
                "%s can only have one %s" % (
                    relation.source,
                    self.render_relation_type(relation.type)
                ))


class ReferencesOlderValidator(Validator):
    def validate(self, relation):
        source, destination = map(ResourceIdSerializer.get_resource_by_id,
                                  [relation.source, relation.destination])
        if source.realm == 'ticket' and destination.realm == 'ticket':
            source, destination = map(
                TicketRelationsSpecifics(self.env)._create_ticket_by_full_id,
                [source, destination])
            if destination['time'] > source['time']:
                raise ValidationError(
                    "Relation %s must reference an older resource." %
                    self.render_relation_type(relation.type)
                )


class BlockerValidator(Validator):
    def validate(self, relation):
        """If a path exists from relation's destination to its source,
         adding the relation will create a cycle.
         """
        rls = RelationsSystem(self.env)
        if not rls.is_blocker(relation.type):
            relation = rls.get_reverted_relation(relation)
        if not relation or not rls.is_blocker(relation.type):
            return

        blockers = ','.join(b for b, is_blocker in rls._blockers.items()
                            if is_blocker)

        path = self._find_path(relation.source,
                               relation.destination,
                               blockers)
        if path:
            cycle_str = map(self.get_resource_name, path)
            error = 'Cycle in ''%s'': %s' % (
                self.render_relation_type(relation.type),
                ' -> '.join(cycle_str))
            error = ValidationError(error)
            error.failed_ids = path
            raise error


class ValidationError(TracError):
    def __init__(self, message, title=None, show_traceback=False):
        super(ValidationError, self).__init__(
            message, title, show_traceback)
        self.failed_ids = []
