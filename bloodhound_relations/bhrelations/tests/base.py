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

from _sqlite3 import OperationalError
from tests.env import MultiproductTestCase
from multiproduct.env import ProductEnvironment
from bhrelations.api import RelationsSystem, EnvironmentSetup
from trac.test import EnvironmentStub, Mock, MockPerm
from trac.ticket import Ticket
from trac.util.datefmt import utc

try:
    from babel import Locale

    locale_en = Locale.parse('en_US')
except ImportError:
    locale_en = None


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
        config_name = RelationsSystem.RELATIONS_CONFIG_NAME
        env.config.set(config_name, 'dependency', 'dependson,dependent')
        env.config.set(config_name, 'dependency.validators',
                       'NoCycles,SingleProduct')
        env.config.set(config_name, 'dependson.blocks', 'true')
        env.config.set(config_name, 'parent_children', 'parent,children')
        env.config.set(config_name, 'parent_children.validators',
                       'OneToMany,SingleProduct,NoCycles')
        env.config.set(config_name, 'children.label', 'Overridden')
        env.config.set(config_name, 'parent.copy_fields',
                       'summary, foo')
        env.config.set(config_name, 'parent.exclusive', 'true')
        env.config.set(config_name, 'multiproduct_relation', 'mprel,mpbackrel')
        env.config.set(config_name, 'oneway', 'refersto')
        env.config.set(config_name, 'duplicate', 'duplicateof,duplicatedby')
        env.config.set(config_name, 'duplicate.validators', 'ReferencesOlder')
        env.config.set(config_name, 'duplicateof.label', 'is a duplicate of')
        env.config.set(config_name, 'duplicatedby.label', 'duplicates')
        env.config.set(config_name, 'blocker', 'blockedby,blocks')
        env.config.set(config_name, 'blockedby.blocks', 'true')

        self.global_env = env
        self._upgrade_mp(self.global_env)
        self._setup_test_log(self.global_env)
        self._load_product_from_data(self.global_env, self.default_product)
        self.env = ProductEnvironment(self.global_env, self.default_product)

        self.req = Mock(href=self.env.href, authname='anonymous', tz=utc,
                        args=dict(action='dummy'),
                        locale=locale_en, lc_time=locale_en)
        self.req.perm = MockPerm()
        self.relations_system = RelationsSystem(self.env)
        self._upgrade_env()

    def tearDown(self):
        self.global_env.reset_db()

    def _upgrade_env(self):
        environment_setup = EnvironmentSetup(self.env)
        try:
            environment_setup.upgrade_environment(self.env.db_transaction)
        except OperationalError:
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
