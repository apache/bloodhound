# -*- coding: utf-8 -*-
#
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

"""Tests for Apache(TM) Bloodhound's product permissions subsystem"""

import unittest

from trac import perm
from trac.tests.perm import DefaultPermissionStoreTestCase

from multiproduct.env import ProductEnvironment
from tests.env import MultiproductTestCase


class ProductDefaultPermissionStoreTestCase(DefaultPermissionStoreTestCase, 
        MultiproductTestCase):

    def setUp(self):
        self.global_env = self._setup_test_env()
        self._upgrade_mp(self.global_env)
        self._setup_test_log(self.global_env)
        self._load_product_from_data(self.env, self.default_product)
        self.env = ProductEnvironment(self.env, self.default_product)

        self.store = perm.DefaultPermissionStore(self.env)

    def test_env_isolation(self):
        global_env = self.global_env
        env = self.env

        self._load_product_from_data(self.global_env, 'tp2')
        env1 = ProductEnvironment(self.global_env, 'tp2')

        global_store = perm.DefaultPermissionStore(global_env)
        store = perm.DefaultPermissionStore(env)
        store1 = perm.DefaultPermissionStore(env1)

        global_env.db_transaction.executemany(
            "INSERT INTO permission VALUES (%s,%s)", 
            [('dev', 'WIKI_MODIFY'),
             ('dev', 'REPORT_ADMIN'),
             ('john', 'dev')])
        env.db_transaction.executemany(
            "INSERT INTO permission VALUES (%s,%s)", 
            [('dev', 'WIKI_VIEW'),
             ('dev', 'REPORT_VIEW'),
             ('john', 'dev')])
        env1.db_transaction.executemany(
            "INSERT INTO permission VALUES (%s,%s)", 
            [('dev', 'TICKET_CREATE'),
             ('dev', 'MILESTONE_VIEW'),
             ('john', 'dev')])

        self.assertEquals(['REPORT_ADMIN', 'WIKI_MODIFY'],
                          sorted(global_store.get_user_permissions('john')))
        self.assertEquals(['REPORT_VIEW', 'WIKI_VIEW'],
                          sorted(store.get_user_permissions('john')))
        self.assertEquals(['MILESTONE_VIEW', 'TICKET_CREATE'],
                          sorted(store1.get_user_permissions('john')))


def test_suite():
    return unittest.makeSuite(ProductDefaultPermissionStoreTestCase,'test')

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

