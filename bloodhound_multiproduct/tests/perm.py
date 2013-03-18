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

from trac.admin.api import AdminCommandError
from trac import perm
from trac.tests.perm import DefaultPermissionStoreTestCase,\
        PermissionSystemTestCase, PermissionCacheTestCase,\
        PermissionPolicyTestCase, TestPermissionPolicy, TestPermissionRequestor

from multiproduct.env import ProductEnvironment
from multiproduct.perm import MultiproductPermissionPolicy
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

class ProductPermissionSystemTestCase(PermissionSystemTestCase,
                                      MultiproductTestCase):
    @property
    def env(self):
        env = getattr(self, '_env', None)
        if env is None:
            self.global_env = self._setup_test_env(enable=[
                    perm.PermissionSystem,
                    perm.DefaultPermissionStore,
                    TestPermissionRequestor])
            self._upgrade_mp(self.global_env)
            self._setup_test_log(self.global_env)
            self._load_product_from_data(self.global_env, self.default_product)
            self._env = env = ProductEnvironment(
                    self.global_env, self.default_product)
        return env

    @env.setter
    def env(self, value):
        pass

    def test_all_permissions(self):
        # PRODUCT_ADMIN meta-permission in product context
        self.assertEqual({'EMAIL_VIEW': True, 'TRAC_ADMIN': True,
                          'TEST_CREATE': True, 'TEST_DELETE': True,
                          'TEST_MODIFY': True,  'TEST_ADMIN': True,
                          'PRODUCT_ADMIN' : True},
                         self.perm.get_user_permissions())

    def test_expand_actions_iter_7467(self):
        # Check that expand_actions works with iterators (#7467)
        # PRODUCT_ADMIN meta-permission in product context
        perms = set(['EMAIL_VIEW', 'TRAC_ADMIN', 'TEST_DELETE', 'TEST_MODIFY',
                     'TEST_CREATE', 'TEST_ADMIN', 'PRODUCT_ADMIN'])
        self.assertEqual(perms, self.perm.expand_actions(['TRAC_ADMIN']))
        self.assertEqual(perms, self.perm.expand_actions(iter(['TRAC_ADMIN'])))


class ProductPermissionCacheTestCase(PermissionCacheTestCase,
                                      MultiproductTestCase):
    @property
    def env(self):
        env = getattr(self, '_env', None)
        if env is None:
            self.global_env = self._setup_test_env(enable=[
                    perm.DefaultPermissionStore,
                    perm.DefaultPermissionPolicy,
                    TestPermissionRequestor])
            self._upgrade_mp(self.global_env)
            self._setup_test_log(self.global_env)
            self._load_product_from_data(self.global_env, self.default_product)
            self._env = env = ProductEnvironment(
                    self.global_env, self.default_product)
        return env

    @env.setter
    def env(self, value):
        pass


class ProductPermissionPolicyTestCase(PermissionPolicyTestCase, 
                                           MultiproductTestCase):
    @property
    def env(self):
        env = getattr(self, '_env', None)
        if env is None:
            self.global_env = self._setup_test_env(enable=[
                    perm.DefaultPermissionStore,
                    perm.DefaultPermissionPolicy,
                    perm.PermissionSystem,
                    TestPermissionPolicy,
                    TestPermissionRequestor,
                    MultiproductPermissionPolicy])
            self._upgrade_mp(self.global_env)
            self._setup_test_log(self.global_env)
            self._load_product_from_data(self.global_env, self.default_product)
            self._env = env = ProductEnvironment(
                    self.global_env, self.default_product)
        return env

    @env.setter
    def env(self, value):
        pass

    def setUp(self):
        super(ProductPermissionPolicyTestCase, self).setUp()

        self.global_env.config.set('trac', 'permission_policies', 
                                   'DefaultPermissionPolicy')
        self.permsys = perm.PermissionSystem(self.env)
        self.global_perm_admin = perm.PermissionAdmin(self.global_env)
        self.product_perm_admin = perm.PermissionAdmin(self.env)

    def tearDown(self):
        self.global_env.reset_db()
        self.global_env = self.env = None

    def test_prepend_mp_policy(self):
        self.assertEqual([MultiproductPermissionPolicy(self.env), self.policy],
                         self.permsys.policies)

    def test_policy_chaining(self):
        self.env.config.set('trac', 'permission_policies', 
                            'TestPermissionPolicy,DefaultPermissionPolicy')
        self.policy.grant('testuser', ['TEST_MODIFY'])
        system = perm.PermissionSystem(self.env)
        system.grant_permission('testuser', 'TEST_ADMIN')

        self.assertEqual(list(system.policies),
                         [MultiproductPermissionPolicy(self.env),
                          self.policy,
                          perm.DefaultPermissionPolicy(self.env)])
        self.assertEqual('TEST_MODIFY' in self.perm, True)
        self.assertEqual('TEST_ADMIN' in self.perm, True)
        self.assertEqual(self.policy.results,
                         {('testuser', 'TEST_MODIFY'): True,
                          ('testuser', 'TEST_ADMIN'): None})

    def test_product_trac_admin_success(self):
        """TRAC_ADMIN in global env also valid in product env
        """
        self.global_perm_admin._do_add('testuser', 'TRAC_ADMIN')
        self.assertTrue(self.perm.has_permission('TRAC_ADMIN'))

    def test_product_trac_admin_fail_local(self):
        """TRAC_ADMIN granted in product env will be ignored
        """
        try:
            # Not needed but added just in case , also for readability
            self.global_perm_admin._do_remove('testuser', 'TRAC_ADMIN')
        except AdminCommandError:
            pass

        # Setting TRAC_ADMIN permission in product scope is in vain
        # since it controls access to critical actions affecting the whole site
        # This will protect the system against malicious actors
        # and / or failures leading to the addition of TRAC_ADMIN permission 
        # in product perm store in spite of obtaining unrighteous super powers.
        # On the other hand this also means that PRODUCT_ADMIN(s) are 
        # able to set user permissions at will without jeopardizing system
        # integrity and stability.
        self.product_perm_admin._do_add('testuser', 'TRAC_ADMIN')
        self.assertFalse(self.perm.has_permission('TRAC_ADMIN'))

    def test_product_owner_perm(self):
        """Product owner automatically granted with PRODUCT_ADMIN
        """
        self.assertIs(self.env.product.owner, None)
        self.assertFalse(self.perm.has_permission('PRODUCT_ADMIN'))

        self.env.product.owner = 'testuser'
        # FIXME: update really needed ?
        self.env.product.update()
        try:
            # Not needed but added just in case , also for readability
            self.global_perm_admin._do_remove('testuser', 'TRAC_ADMIN')
        except AdminCommandError:
            pass
        self.perm._cache.clear()

        self.assertTrue(self.perm.has_permission('PRODUCT_ADMIN'))
        self.assertFalse(self.perm.has_permission('TRAC_ADMIN'))


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ProductDefaultPermissionStoreTestCase, 
                                     'test'))
    suite.addTest(unittest.makeSuite(ProductPermissionSystemTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ProductPermissionCacheTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ProductPermissionPolicyTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

