
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

"""Tests for Apache(TM) Bloodhound's tickets API in product environments"""

import unittest

from trac.perm import PermissionCache, PermissionSystem
from trac.test import Mock
from trac.ticket.api import TicketSystem
from trac.ticket.tests.api import TicketSystemTestCase

from multiproduct.env import ProductEnvironment
from tests.env import MultiproductTestCase

class ProductTicketSystemTestCase(TicketSystemTestCase, MultiproductTestCase):

    def setUp(self):
        self.global_env = self._setup_test_env(create_folder=False)
        self._upgrade_mp(self.global_env)
        self._setup_test_log(self.global_env)
        self._load_product_from_data(self.global_env, self.default_product)
        self.env = ProductEnvironment(self.global_env, self.default_product)

        self.perm = PermissionSystem(self.env)
        self.ticket_system = TicketSystem(self.env)
        self.req = Mock()

    def tearDown(self):
        self.global_env.reset_db()

    def test_custom_field_isolation(self):
        self.env.config.set('ticket-custom', 'test', 'select')
        self.env.config.set('ticket-custom', 'test.label', 'Test')
        self.env.config.set('ticket-custom', 'test.value', '1')
        self.env.config.set('ticket-custom', 'test.options', 'option1|option2')

        self.global_env.config.set('ticket-custom', 'test', 'text')
        self.global_env.config.set('ticket-custom', 'test.label', 'Test')
        self.global_env.config.set('ticket-custom', 'test.value', 'Foo bar')
        self.global_env.config.set('ticket-custom', 'test.format', 'wiki')

        product_fields = TicketSystem(self.env).get_custom_fields()
        global_fields = TicketSystem(self.global_env).get_custom_fields()

        self.assertEqual({'name': 'test', 'type': 'select', 'label': 'Test',
                          'value': '1', 'options': ['option1', 'option2'],
                          'order': 0},
                         product_fields[0])
        self.assertEqual({'name': 'test', 'type': 'text', 'label': 'Test',
                          'value': 'Foo bar', 'order': 0, 'format': 'wiki'},
                         global_fields[0])

    def test_available_actions_isolation(self):
        # Grant TICKET_CREATE in product environment ...
        self.perm.grant_permission('anonymous', 'TICKET_CREATE')
        self.req.perm = PermissionCache(self.env)
        self.assertEqual(['leave', 'reopen'],
                         self._get_actions({'status': 'closed'}))

        # ... but no perms in global environment
        self.req.perm = PermissionCache(self.global_env)
        product_env = self.env
        try:
            self.env = self.global_env
            self.assertEqual(['leave'], self._get_actions({'status': 'closed'}))
        finally:
            self.env = product_env

def test_suite():
    return unittest.TestSuite([
            unittest.makeSuite(ProductTicketSystemTestCase,'test'),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

