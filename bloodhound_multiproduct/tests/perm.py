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
from trac.resource import Neighborhood
from trac.test import Mock
from trac.tests.perm import DefaultPermissionStoreTestCase,\
        PermissionSystemTestCase, PermissionCacheTestCase,\
        PermissionPolicyTestCase, TestPermissionPolicy, TestPermissionRequestor

from multiproduct.api import MultiProductSystem
from multiproduct.env import ProductEnvironment
from multiproduct.model import Product
from multiproduct.perm import MultiproductPermissionPolicy, sudo
from tests.env import MultiproductTestCase

# DefaultPermission policy has its own cache that causes
# test_product_trac_admin_actions to fail sometimes.
perm.DefaultPermissionPolicy.CACHE_EXPIRY = 0


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


class ProductNeighborhoodPermissionCacheTestCase(ProductPermissionCacheTestCase,
                                      MultiproductTestCase):
    @property
    def env(self):
        env = getattr(self, '_env', None)
        if env is None:
            self.global_env = self._setup_test_env(enable=[
                    perm.DefaultPermissionStore,
                    perm.DefaultPermissionPolicy,
                    MultiProductSystem,
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

    def setUp(self):
        ProductPermissionCacheTestCase.setUp(self)
        nbh = Neighborhood('product', self.default_product)
        resource = nbh.child(None, None)
        self.perm = perm.PermissionCache(self.global_env, 'testuser', resource)


class SudoTestCase(ProductPermissionCacheTestCase):
    loader = unittest.defaultTestLoader
    tcnames = loader.getTestCaseNames(ProductPermissionCacheTestCase)
    _gen_tests = {}

    def test_sudo_wrong_context(self):
        sudoperm = sudo(None, 'EMAIL_VIEW', ['TEST_ADMIN'])

        with self.assertRaises(RuntimeError) as test_cm:
            sudoperm.has_permission('TEST_MODIFY')
        self.assertEqual('Permission check out of context', 
                         str(test_cm.exception))

        with self.assertRaises(ValueError) as test_cm:
            with sudoperm:
                pass
        self.assertEquals('Context manager not bound to request object',
                          str(test_cm.exception))

    def test_sudo_fail_require(self):
        sudoperm = sudo(None, 'EMAIL_VIEW', ['TEST_ADMIN'])

        sudoperm.perm = self.perm
        with self.assertRaises(perm.PermissionError) as test_cm:
            sudoperm.require('TRAC_ADMIN')
        self.assertEqual('EMAIL_VIEW', test_cm.exception.action)

    def test_sudo_grant_meta_perm(self):
        self.env.parent.enable_component(perm.PermissionSystem)
        self.env.enable_component(perm.PermissionSystem)
        del self.env.parent.enabled[perm.PermissionSystem]
        del self.env.enabled[perm.PermissionSystem]

        sudoperm = sudo(None, 'TEST_CREATE', ['TRAC_ADMIN'])
        sudoperm.perm = self.perm
        
        self.assertTrue(sudoperm.has_permission('EMAIL_VIEW'))

    def test_sudo_ambiguous(self):
        with self.assertRaises(ValueError) as test_cm:
            sudo(None, 'TEST_MODIFY', ['TEST_MODIFY', 'TEST_DELETE'], 
                 ['TEST_MODIFY', 'TEST_CREATE'])
        self.assertEquals('Impossible to grant and revoke (TEST_MODIFY)', 
                          str(test_cm.exception))

        with self.assertRaises(ValueError) as test_cm:
            sudoperm = sudo(None, 'TEST_MODIFY', ['TEST_ADMIN'], 
                 ['TEST_MODIFY', 'TEST_CREATE'])
            sudoperm.perm = self.perm
        self.assertEquals('Impossible to grant and revoke '
                          '(TEST_CREATE, TEST_MODIFY)', 
                          str(test_cm.exception))

        with self.assertRaises(ValueError) as test_cm:
            req = Mock(perm=self.perm)
            sudo(req, 'TEST_MODIFY', ['TEST_ADMIN'], 
                 ['TEST_MODIFY', 'TEST_CREATE'])
        self.assertEquals('Impossible to grant and revoke '
                          '(TEST_CREATE, TEST_MODIFY)', 
                          str(test_cm.exception))

    # Sudo permission context equivalent to  permissions cache
    # if there's no action to require, allow or deny.
    def _test_with_sudo_rules(tcnm, prefix, grant):
        target = getattr(ProductPermissionCacheTestCase, tcnm)

        def _sudo_eq_checker(self):
            for action in grant:
                self.perm_system.revoke_permission('testuser', action)
            realperm = self.perm
            self.perm = sudo(None, [], grant, [])
            self.perm.perm = realperm
            target(self)

        _sudo_eq_checker.func_name = prefix + tcnm
        return _sudo_eq_checker

    for tcnm in tcnames:
        f1 = _test_with_sudo_rules(tcnm, '', [])
        f2 = _test_with_sudo_rules(tcnm, 'test_sudo_partial_', 
                                   ['TEST_MODIFY'])
        f3 = _test_with_sudo_rules(tcnm, 'test_sudo_full_', 
                                   ['TEST_MODIFY', 'TEST_ADMIN'])
        for f in (f1, f2, f3):
            _gen_tests[f.func_name] = f

    del loader, tcnames, tcnm, f1, f2, f3

list(setattr(SudoTestCase, tcnm, f)
     for tcnm, f in SudoTestCase._gen_tests.iteritems())


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

    def test_product_trac_admin_actions(self):
        """Allow all actions in product scope for TRAC_ADMIN
        """
        self.global_perm_admin._do_add('testuser', 'TRAC_ADMIN')

        all_actions = self.permsys.get_actions()
        self.assertEquals(['TEST_CREATE', 'EMAIL_VIEW', 'TRAC_ADMIN',
                           'TEST_DELETE', 'TEST_MODIFY', 'PRODUCT_ADMIN',
                           'TEST_ADMIN'], all_actions)
        self.assertEquals({}, self.permsys.get_user_permissions('testuser'))
        for action in all_actions:
            self.assertTrue(self.perm.has_permission(action),
                            'Check for permission action %s' % (action,))
        self.assertFalse(self.perm.has_permission('UNKNOWN_PERM'))

        # Clear permissions cache and retry 
        self.perm._cache.clear()
        self.global_perm_admin._do_remove('testuser', 'TRAC_ADMIN')

        all_actions = self.permsys.get_actions()
        self.assertEquals(['TEST_CREATE', 'EMAIL_VIEW', 'TRAC_ADMIN',
                           'TEST_DELETE', 'TEST_MODIFY', 'PRODUCT_ADMIN',
                           'TEST_ADMIN'], all_actions)
        self.assertEquals({}, self.permsys.get_user_permissions('testuser'))
        for action in all_actions:
            self.assertFalse(self.perm.has_permission(action),
                            'Check for permission action %s' % (action,))

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

    def test_new_product_perm(self):
        """Only product owner and TRAC_ADMIN will access new product
        """
        newproduct = Product(self.global_env)
        newproduct.prefix = 'NEW'
        newproduct.name = 'New product'
        newproduct.owner = 'owneruser'
        newproduct.insert()

        env = ProductEnvironment(self.global_env, newproduct)
        self.global_perm_admin._do_add('adminuser', 'TRAC_ADMIN')
        admin_perm = perm.PermissionCache(env, 'adminuser')
        owner_perm = perm.PermissionCache(env, 'owneruser')
        user_perm = perm.PermissionCache(env, 'testuser')
        global_permsys = perm.PermissionSystem(self.global_env)
        permsys = perm.PermissionSystem(env)

        self.assertEquals({'EMAIL_VIEW': True, 'TEST_ADMIN': True,
                           'TEST_CREATE': True, 'TEST_DELETE': True,
                           'TEST_MODIFY': True, 'TRAC_ADMIN' : True},
                          global_permsys.get_user_permissions('adminuser'))
        self.assertEquals({}, global_permsys.get_user_permissions('owneruser'))
        self.assertEquals({}, global_permsys.get_user_permissions('testuser'))
        self.assertEquals({}, permsys.get_user_permissions('adminuser'))
        self.assertEquals({}, permsys.get_user_permissions('owneruser'))
        self.assertEquals({}, permsys.get_user_permissions('testuser'))

        all_actions = self.permsys.get_actions()
        all_actions.remove('TRAC_ADMIN')
        for action in all_actions:
            self.assertTrue(admin_perm.has_permission(action))
            self.assertTrue(owner_perm.has_permission(action))
            self.assertFalse(user_perm.has_permission(action))

        self.assertTrue(admin_perm.has_permission('TRAC_ADMIN'))
        self.assertFalse(owner_perm.has_permission('TRAC_ADMIN'))
        self.assertFalse(user_perm.has_permission('TRAC_ADMIN'))


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ProductDefaultPermissionStoreTestCase, 
                                     'test'))
    suite.addTest(unittest.makeSuite(ProductPermissionSystemTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ProductPermissionCacheTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ProductNeighborhoodPermissionCacheTestCase,
                                     'test'))
    suite.addTest(unittest.makeSuite(ProductPermissionPolicyTestCase, 'test'))

    suite.addTest(unittest.makeSuite(SudoTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

