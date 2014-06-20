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

from tests.env import MultiproductTestCase
from trac.test import EnvironmentStub, Mock, MockPerm
from trac.ticket import Ticket
from trac.util.datefmt import utc

from multiproduct.env import ProductEnvironment

from bhrelations.api import EnvironmentSetup, RelationsSystem, \
                            RELATIONS_CONFIG_NAME

try:
    from babel import Locale
    locale_en = Locale.parse('en_US')
except ImportError:
    locale_en = None


PARENT = "parent"
CHILD = "child"
REFERS_TO = "refersto"
DEPENDS_ON = "dependson"
DEPENDENCY_OF = "dependent"
DUPLICATE_OF = "duplicateof"
DUPLICATED_BY = "duplicatedby"
BLOCKED_BY = "blockedby"
BLOCKS = "blocks"
MULTIPRODUCT_REL = "mprel"
MULTIPRODUCT_BACKREL = "mpbackrel"


class BaseRelationsTestCase(MultiproductTestCase):
    def setUp(self, enabled=()):
        env = EnvironmentStub(
            default_data=True,
            enable=(['trac.*', 'multiproduct.*', 'bhrelations.*'] +
                    list(enabled))
        )
        env.config.set('bhrelations', 'global_validators',
                       'NoSelfReferenceValidator,ExclusiveValidator,'
                       'BlockerValidator')
        env.config.set('bhrelations', 'duplicate_relation',
                       'duplicateof')
        config_name = RELATIONS_CONFIG_NAME
        env.config.set(config_name, 'dependency',
                       ','.join([DEPENDS_ON, DEPENDENCY_OF]))
        env.config.set(config_name, 'dependency.validators',
                       'NoCycles,SingleProduct')
        env.config.set(config_name, 'dependson.blocks', 'true')
        env.config.set(config_name, 'parent_children',
                       ','.join([PARENT, CHILD]))
        env.config.set(config_name, 'parent_children.validators',
                       'OneToMany,SingleProduct,NoCycles')
        env.config.set(config_name, 'children.label', 'Overridden')
        env.config.set(config_name, 'parent.copy_fields',
                       'summary, foo')
        env.config.set(config_name, 'parent.exclusive', 'true')
        env.config.set(config_name, 'multiproduct_relation',
                       ','.join([MULTIPRODUCT_REL, MULTIPRODUCT_BACKREL]))
        env.config.set(config_name, 'oneway', REFERS_TO)
        env.config.set(config_name, 'duplicate',
                       ','.join([DUPLICATE_OF, DUPLICATED_BY]))
        env.config.set(config_name, 'duplicate.validators', 'ReferencesOlder')
        env.config.set(config_name, 'duplicateof.label', 'is a duplicate of')
        env.config.set(config_name, 'duplicatedby.label', 'duplicates')
        env.config.set(config_name, 'blocker', ','.join([BLOCKED_BY, BLOCKS]))
        env.config.set(config_name, 'blockedby.blocks', 'true')

        self.global_env = env
        self._upgrade_mp(self.global_env)
        self._setup_test_log(self.global_env)
        self._load_product_from_data(self.global_env, self.default_product)
        self.env = ProductEnvironment(self.global_env, self.default_product)

        self.req = Mock(href=self.env.href, authname='anonymous', tz=utc,
                        args=dict(action='dummy'),
                        locale=locale_en, lc_time=locale_en,
                        chrome={'warnings': []})
        self.req.perm = MockPerm()
        self.relations_system = RelationsSystem(self.env)
        self._upgrade_env()

    def tearDown(self):
        self.global_env.reset_db()

    def _upgrade_env(self):
        environment_setup = EnvironmentSetup(self.env)
        try:
            environment_setup.upgrade_environment(self.env.db_transaction)
        except self.env.db_exc.OperationalError:
            # table remains but database version is deleted
            pass

    @classmethod
    def _insert_ticket(cls, env, summary, **kw):
        """Helper for inserting a ticket into the database"""
        ticket = Ticket(env)
        ticket["summary"] = summary
        for k, v in kw.items():
            ticket[k] = v
        return ticket.insert()

    def _insert_and_load_ticket(self, summary, **kw):
        return Ticket(self.env, self._insert_ticket(self.env, summary, **kw))

    def _insert_and_load_ticket_with_env(self, env, summary, **kw):
        return Ticket(env, self._insert_ticket(env, summary, **kw))

    def add_relation(self, source, reltype, destination, *args, **kwargs):
        return self.relations_system.add(source, destination, reltype,
                                         *args, **kwargs)

    def get_relations(self, ticket):
        return self.relations_system.get_relations(ticket)

    def delete_relation(self, relation):
        self.relations_system.delete(relation["relation_id"])
