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
from bhdashboard.model import ModelBase
from trac.resource import Resource


class Relation(ModelBase):
    """The Relation table"""
    RELATION_ID_DELIMITER = u","

    _meta = {'table_name':'bloodhound_relations',
            'object_name':'Relation',
            'key_fields':['source', 'type', 'destination'],
            'non_key_fields':['comment'],
            'no_change_fields':['source', 'destination', 'type'],
            'unique_fields':[],
            # 'auto_inc_fields': ['id'],
            }

    # _meta = {'table_name':'bloodhound_relations',
    #         'object_name':'Relation',
    #         'key_fields':['id'],
    #         'non_key_fields':['source', 'destination', 'type', 'comment'],
    #         'no_change_fields':['source', 'destination', 'type'],
    #         'unique_fields':['source', 'destination', 'type'],
    #         'auto_inc_fields': ['id'],
    #         }

    @property
    def resource(self):
        """Allow Relation to be treated as a Resource"""
        return Resource('relation', self.prefix)

    def clone_reverted(self, type):
        relation = Relation(self._env)
        relation.source = self.destination
        relation.destination = self.source
        relation.comment = self.comment
        relation.type = type
        return relation

    def get_relation_id(self):
        return self.RELATION_ID_DELIMITER.join((
            self.source,
            self.destination,
            self.type))

    @classmethod
    def _parse_relation_id(cls, relation_id):
        source, destination, relation_type = relation_id.split(
            cls.RELATION_ID_DELIMITER)
        return source, destination, relation_type

    @classmethod
    def load_by_relation_id(cls, env, relation_id):
        source, destination, relation_type = cls._parse_relation_id(
            relation_id)
        return Relation(env, keys=dict(
            source=source,
            destination=destination,
            type=relation_type
            ))
