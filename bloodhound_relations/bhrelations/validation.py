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
    ResourceIdSerializer


class Validator(Component):
    implements(IRelationValidator)

    def validate(self, relation):
        raise NotImplementedError

    def render_relation_type(self, end):
        return RelationsSystem(self.env)._labels[end]

    def get_resource_name(self, resource_id):
        resource = ResourceIdSerializer.get_resource_by_id(resource_id)
        return get_resource_shortname(self.env, resource)


class NoCyclesValidator(Validator):
    def validate(self, relation):
        """If a path exists from relation's destination to its source,
         adding the relation will create a cycle.
         """
        path = self._find_path(relation.destination,
                               relation.source,
                               relation.type)
        if path:
            cycle_str = map(self.get_resource_name, path)
            error = 'Cycle in ''%s'': %s' % (
                self.render_relation_type(relation.type),
                ' -> '.join(cycle_str))
            error = ValidationError(error)
            error.failed_ids = path
            raise error

    def _find_path(self, source, destination, relation_type):
        known_nodes = set()
        new_nodes = set([source])
        paths = {(source, source): [source]}

        while new_nodes:
            known_nodes = set.union(known_nodes, new_nodes)
            with self.env.db_query as db:
                relations = dict(db("""
                    SELECT source, destination
                      FROM bloodhound_relations
                     WHERE type = '%(relation_type)s'
                       AND source IN (%(new_nodes)s)
                """ % dict(
                    relation_type=relation_type,
                    new_nodes=', '.join("'%s'" % n for n in new_nodes))
                ))
            new_nodes = set(relations.values()) - known_nodes
            for s, d in relations.items():
                paths[(source, d)] = paths[(source, s)] + [d]
            if destination in new_nodes:
                return paths[(source, destination)]


class ExclusiveValidator(Validator):
    def validate(self, relation):
        rls = RelationsSystem(self.env)
        incompatible_relations = [
            rel for rel in rls._select_relations(relation.source)
            if rel.destination == relation.destination
        ] + [
            rel for rel in rls._select_relations(relation.destination)
            if rel.destination == relation.source
        ]
        if incompatible_relations:
            raise ValidationError(
                "Relation %s is incompatible with the "
                "following existing relations: %s" % (
                    self.render_relation_type(relation.type),
                    ','.join(map(str, incompatible_relations))
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
                    relation.destination,
                    self.render_relation_type(relation.type)
                ))


class ValidationError(TracError):
    def __init__(self, message, title=None, show_traceback=False):
        super(ValidationError, self).__init__(
            message, title, show_traceback)
        self.failed_ids = []
