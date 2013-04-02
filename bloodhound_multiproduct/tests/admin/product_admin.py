
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

"""Tests for Apache(TM) Bloodhound's product admin"""

import sys
import unittest
from wsgiref.util import setup_testing_defaults

from trac.admin.api import IAdminPanelProvider
from trac.admin.web_ui import AdminModule, PluginAdminPanel
from trac.core import Component, implements
from trac.perm import DefaultPermissionPolicy, DefaultPermissionStore, \
                      PermissionCache, PermissionSystem
from trac.tests.perm import TestPermissionRequestor
from trac.web.api import HTTP_STATUS, HTTPForbidden, HTTPNotFound, \
                         IRequestFilter, RequestDone, Request
from trac.web.main import RequestDispatcher

from multiproduct import api, product_admin
from multiproduct.env import ProductEnvironment
from multiproduct.product_admin import IProductAdminAclContributor, \
                                       ProductAdminModule
from tests.env import MultiproductTestCase

class TestAdminHandledException(Exception):
    product = None
    category = None
    page = None
    path_info = None
    admin_panels = None

class TestAdminPanel(Component):
    implements(IAdminPanelProvider, IRequestFilter)

    # IAdminPanelProvider methods
    def get_admin_panels(self, req):
        if 'TRAC_ADMIN' in req.perm:
            yield 'testcat1', 'Test category 1', 'panel1', 'Test panel 1'
            yield 'testcat1', 'Test category 1', 'panel2', 'Test panel 2'
            yield 'testcat1', 'Test category 1', 'panel3', 'Test panel 3'
    
            yield 'testcat2', 'Test category 2', 'panel1', 'Test panel 1'
            yield 'testcat2', 'Test category 2', 'panel_2', 'Test panel 2'
            yield 'testcat2', 'Test category 2', 'panel-3', 'Test panel 3'
    
            yield 'testcat3', 'Test category 3', 'panel1', 'Test panel 1'
            yield 'testcat3', 'Test category 3', 'panel2', 'Test panel 2'

    def render_admin_panel(self, req, category, page, path_info):
        req.perm.require('TRAC_ADMIN')
        return 'test.html', {'path_info' : path_info}

    def pre_process_request(self, req, handler):
        return handler

    def post_process_request(self, req, template, data, content_type):
        if sys.exc_info() == (None, None, None):
            exc = TestAdminHandledException()
            exc.product = self.env.product.prefix \
                     if isinstance(self.env, ProductEnvironment) \
                     else ''
            exc.category = data.get('active_cat')
            exc.page = data.get('active_panel')
            exc.path_info = data.get('path_info')
            exc.admin_panels = data.get('panels')
            raise exc
        else:
            return template, data, content_type


class PanelsWhitelist(Component):
    implements(product_admin.IProductAdminAclContributor)

    # IProductAdminAclContributor methods
    def enable_product_admin_panels(self):
        yield 'testcat1', 'panel1'
        yield 'testcat1', 'panel3'
        yield 'testcat2', 'panel3'
        yield 'general', 'plugin'


class SectionWhitelist(Component):
    implements(product_admin.IProductAdminAclContributor)

    # IProductAdminAclContributor methods
    def enable_product_admin_panels(self):
        yield 'testcat3', '*'

class BaseProductAdminPanelTestCase(MultiproductTestCase):
    def setUp(self):
        self._mp_setup(enable=[AdminModule, DefaultPermissionPolicy,
                               DefaultPermissionStore, PermissionSystem,
                               PluginAdminPanel, RequestDispatcher, 
                               api.MultiProductSystem,
                               product_admin.ProductAdminModule,
                               PanelsWhitelist, SectionWhitelist, 
                               TestAdminPanel, TestPermissionRequestor])
        self.global_env = self.env
        self.env = ProductEnvironment(self.global_env, self.default_product)

        ProductAdminModule = product_admin.ProductAdminModule
        self.global_product_admin = ProductAdminModule(self.global_env)
        self.product_admin = ProductAdminModule(self.env)

    def tearDown(self):
        self.global_env.reset_db()
        self.env = self.global_env = None
        self.product_admin = self.global_product_admin = None


class ProductAdminSetupTestCase(BaseProductAdminPanelTestCase):
    ALL_PANELS = [('testcat1', 'panel1'), ('testcat1', 'panel2'), 
                  ('testcat1', 'panel3'), ('testcat2', 'panel_1'), 
                  ('testcat2', 'panel-2'), ('testcat2', 'panel3'), 
                  ('testcat3', 'panel1'), ('testcat3', 'panel2'), 
                  ('general', 'plugin'), ]

    def test_init_whitelist(self):
        self.assertEqual({}, self.global_product_admin.acl)
        self.assertEqual({'testcat3' : True,
                          ('testcat1', 'panel1') : True,
                          ('testcat1', 'panel3'): True,
                          ('testcat2', 'panel3'): True,
                          ('general', 'plugin') : True,}, 
                         self.product_admin.acl)
        self.assertTrue(all(not self.global_product_admin._check_panel(c, p)
                            for c, p in self.ALL_PANELS))
        self.assertTrue(self.product_admin._check_panel('testcat1', 'panel1'))
        self.assertFalse(self.product_admin._check_panel('testcat1', 'panel2'))
        self.assertTrue(self.product_admin._check_panel('testcat1', 'panel3'))
        self.assertFalse(self.product_admin._check_panel('testcat2', 'panel_1'))
        self.assertFalse(self.product_admin._check_panel('testcat2', 'panel-2'))
        self.assertTrue(self.product_admin._check_panel('testcat2', 'panel3'))
        self.assertTrue(self.product_admin._check_panel('testcat3', 'panel1'))
        self.assertTrue(self.product_admin._check_panel('testcat3', 'panel2'))
        self.assertFalse(self.product_admin._check_panel('general', 'plugin'))
        self.assertFalse(self.product_admin._check_panel('other', 'panel'))

    def test_init_blacklist(self):
        self.global_env.config.set('multiproduct', 'admin_blacklist', 
                                   'testcat1:panel1,testcat3:panel2')
        self.env.config.set('multiproduct', 'admin_blacklist', 
                            'testcat1:panel3,testcat3:panel1,testcat2:*')

        self.assertEqual(['testcat1:panel1','testcat3:panel2'],
                          self.global_product_admin.raw_blacklist)
        self.assertEqual(['testcat1:panel3','testcat3:panel1','testcat2:*'],
                         self.product_admin.raw_blacklist)

        self.assertEqual({}, self.global_product_admin.acl)
        self.assertEqual({'testcat3' : True,
                          'testcat2' : False,
                          ('testcat1', 'panel1') : True,
                          ('testcat1', 'panel3'): False,
                          ('testcat2', 'panel3'): True,
                          ('testcat3', 'panel1'): False,
                          ('general', 'plugin'): True,}, 
                         self.product_admin.acl)

        self.assertTrue(all(not self.global_product_admin._check_panel(c, p)
                            for c, p in self.ALL_PANELS))
        self.assertTrue(self.product_admin._check_panel('testcat1', 'panel1'))
        self.assertFalse(self.product_admin._check_panel('testcat1', 'panel2'))
        self.assertFalse(self.product_admin._check_panel('testcat1', 'panel3'))
        self.assertFalse(self.product_admin._check_panel('testcat2', 'panel_1'))
        self.assertFalse(self.product_admin._check_panel('testcat2', 'panel-2'))
        self.assertFalse(self.product_admin._check_panel('testcat2', 'panel3'))
        self.assertFalse(self.product_admin._check_panel('testcat3', 'panel1'))
        self.assertTrue(self.product_admin._check_panel('testcat3', 'panel2'))
        self.assertFalse(self.product_admin._check_panel('general', 'plugin'))
        self.assertFalse(self.product_admin._check_panel('other', 'panel'))


class ProductAdminDispatchTestCase(BaseProductAdminPanelTestCase):
    maxDiff = None

    def setUp(self):
        BaseProductAdminPanelTestCase.setUp(self)
        self.global_env.config.set('multiproduct', 'admin_blacklist', 
                                   'testcat1:panel1,testcat3:panel2')
        self.env.config.set('multiproduct', 'admin_blacklist', 
                            'testcat1:panel3,testcat3:panel1,testcat2:*')
        global_permsys = PermissionSystem(self.global_env)
        permsys = PermissionSystem(self.env)

        global_permsys.grant_permission('adminuser', 'TRAC_ADMIN')
        global_permsys.grant_permission('prodadmin', 'PRODUCT_ADMIN')
        global_permsys.grant_permission('testuser', 'TEST_ADMIN')
        permsys.grant_permission('prodadmin', 'PRODUCT_ADMIN')
        permsys.grant_permission('testuser', 'TEST_ADMIN')

        self.req = self._get_request_obj()

    def tearDown(self):
        BaseProductAdminPanelTestCase.tearDown(self)
        self.req = None

    def _get_request_obj(self):
        environ = {}
        setup_testing_defaults(environ)

        def start_response(status, headers):
            return lambda body: None

        req = Request(environ, start_response)
        return req

    def _dispatch(self, req, env):
        req.perm = PermissionCache(env, req.authname)
        return RequestDispatcher(env).dispatch(req)

    GLOBAL_PANELS = [
            {'category': {'id': 'general', 'label': 'General'},
             'panel': {'id': 'plugin', 'label': 'Plugins'}},
            {'category': {'id': 'testcat1', 'label': 'Test category 1'},
             'panel': {'id': 'panel1', 'label': 'Test panel 1'}},
            {'category': {'id': 'testcat1', 'label': 'Test category 1'},
             'panel': {'id': 'panel2', 'label': 'Test panel 2'}},
            {'category': {'id': 'testcat1', 'label': 'Test category 1'},
             'panel': {'id': 'panel3', 'label': 'Test panel 3'}},
            {'category': {'id': 'testcat2', 'label': 'Test category 2'},
             'panel': {'id': 'panel-3', 'label': 'Test panel 3'}},
            {'category': {'id': 'testcat2', 'label': 'Test category 2'},
             'panel': {'id': 'panel1', 'label': 'Test panel 1'}},
            {'category': {'id': 'testcat2', 'label': 'Test category 2'},
             'panel': {'id': 'panel_2', 'label': 'Test panel 2'}},
            {'category': {'id': 'testcat3', 'label': 'Test category 3'},
             'panel': {'id': 'panel1', 'label': 'Test panel 1'}},
            {'category': {'id': 'testcat3', 'label': 'Test category 3'},
             'panel': {'id': 'panel2', 'label': 'Test panel 2'}}]
    PRODUCT_PANELS_ALL = [
            {'category': {'id': 'testcat1', 'label': 'Test category 1'},
             'panel': {'id': 'panel1', 'label': 'Test panel 1'}},
            {'category': {'id': 'testcat1', 'label': 'Test category 1'},
             'panel': {'id': 'panel2', 'label': 'Test panel 2'}},
            {'category': {'id': 'testcat1', 'label': 'Test category 1'},
             'panel': {'id': 'panel3', 'label': 'Test panel 3'}},
            {'category': {'id': 'testcat2', 'label': 'Test category 2'},
             'panel': {'id': 'panel-3', 'label': 'Test panel 3'}},
            {'category': {'id': 'testcat2', 'label': 'Test category 2'},
             'panel': {'id': 'panel1', 'label': 'Test panel 1'}},
            {'category': {'id': 'testcat2', 'label': 'Test category 2'},
             'panel': {'id': 'panel_2', 'label': 'Test panel 2'}},
            {'category': {'id': 'testcat3', 'label': 'Test category 3'},
             'panel': {'id': 'panel1', 'label': 'Test panel 1'}},
            {'category': {'id': 'testcat3', 'label': 'Test category 3'},
             'panel': {'id': 'panel2', 'label': 'Test panel 2'}}]
    PRODUCT_PANELS_ALLOWED = [
            {'category': {'id': 'testcat1', 'label': 'Test category 1'},
             'panel': {'id': 'panel1', 'label': 'Test panel 1'}},
            {'category': {'id': 'testcat3', 'label': 'Test category 3'},
             'panel': {'id': 'panel2', 'label': 'Test panel 2'}}]

    # TRAC_ADMIN
    def test_tracadmin_global_panel(self):
        """Test admin panel with TRAC_ADMIN in global env
        """
        req = self.req
        req.authname = 'adminuser'
        req.environ['PATH_INFO'] = '/admin/testcat1/panel1/some/path'
        with self.assertRaises(TestAdminHandledException) as test_cm:
            self._dispatch(req, self.global_env)

        exc = test_cm.exception
        self.assertEqual('', exc.product)
        self.assertEqual('testcat1', exc.category)
        self.assertEqual('panel1', exc.page)
        self.assertEqual('some/path', exc.path_info)
        self.assertEqual(self.GLOBAL_PANELS, exc.admin_panels)

    def test_tracadmin_global_plugins(self):
        """Plugin admin panel with TRAC_ADMIN in global env
        """
        req = self.req
        req.authname = 'adminuser'
        req.environ['PATH_INFO'] = '/admin/general/plugin'
        # Plugin admin panel looked up but disabled
        with self.assertRaises(TestAdminHandledException) as test_cm:
            self._dispatch(req, self.global_env)

        exc = test_cm.exception
        self.assertEqual(self.GLOBAL_PANELS, exc.admin_panels)

    def test_tracadmin_product_panel_blacklist(self):
        """Test blacklisted admin panel with TRAC_ADMIN in product env
        """
        req = self.req
        req.authname = 'adminuser'
        req.environ['PATH_INFO'] = '/admin/testcat3/panel1/some/path'
        with self.assertRaises(TestAdminHandledException) as test_cm:
            self._dispatch(req, self.env)

        exc = test_cm.exception
        self.assertEqual(self.default_product, exc.product)
        self.assertEqual('testcat3', exc.category)
        self.assertEqual('panel1', exc.page)
        self.assertEqual('some/path', exc.path_info)
        self.assertEqual(self.PRODUCT_PANELS_ALL, exc.admin_panels)

    def test_tracadmin_product_panel_whitelist(self):
        """Test whitelisted admin panel with TRAC_ADMIN in product env
        """
        req = self.req
        req.authname = 'adminuser'
        req.environ['PATH_INFO'] = '/admin/testcat1/panel1/some/path'
        with self.assertRaises(TestAdminHandledException) as test_cm:
            self._dispatch(req, self.env)

        exc = test_cm.exception
        self.assertEqual(self.default_product, exc.product)
        self.assertEqual('testcat1', exc.category)
        self.assertEqual('panel1', exc.page)
        self.assertEqual('some/path', exc.path_info)
        self.assertEqual(self.PRODUCT_PANELS_ALL, exc.admin_panels)

    def test_tracadmin_product_plugins(self):
        """Plugin admin panel with TRAC_ADMIN in global env
        """
        req = self.req
        req.authname = 'adminuser'
        req.environ['PATH_INFO'] = '/admin/general/plugin'
        # Plugin admin panel not available in product context
        with self.assertRaises(HTTPNotFound):
            self._dispatch(req, self.env)

    # PRODUCT_ADMIN
    def test_productadmin_global_panel_whitelist(self):
        """Test whitelisted admin panel with PRODUCT_ADMIN in product env
        """
        req = self.req
        req.authname = 'prodadmin'
        req.environ['PATH_INFO'] = '/admin/testcat1/panel1/some/path'
        with self.assertRaises(HTTPNotFound):
            self._dispatch(req, self.global_env)

    def test_productadmin_global_panel_blacklist(self):
        """Test blacklisted admin panel with PRODUCT_ADMIN in product env
        """
        req = self.req
        req.authname = 'prodadmin'
        req.environ['PATH_INFO'] = '/admin/testcat3/panel1/some/path'
        with self.assertRaises(HTTPNotFound):
            self._dispatch(req, self.global_env)

    def test_productadmin_global_panel_norules(self):
        """Test unspecified admin panel with PRODUCT_ADMIN in product env
        """
        req = self.req
        req.authname = 'prodadmin'
        req.environ['PATH_INFO'] = '/admin/testcat1/panel2/some/path'
        with self.assertRaises(HTTPNotFound):
            self._dispatch(req, self.global_env)

    def test_productadmin_global_plugins(self):
        """Plugin admin panel with PRODUCT_ADMIN in global env
        """
        req = self.req
        req.authname = 'prodadmin'
        req.environ['PATH_INFO'] = '/admin/general/plugin'
        with self.assertRaises(HTTPNotFound):
            self._dispatch(req, self.global_env)

    def test_productadmin_product_panel_whitelist(self):
        """Test whitelisted admin panel with PRODUCT_ADMIN in product env
        """
        req = self.req
        req.authname = 'prodadmin'
        req.environ['PATH_INFO'] = '/admin/testcat1/panel1/some/path'
        with self.assertRaises(TestAdminHandledException) as test_cm:
            self._dispatch(req, self.env)

        exc = test_cm.exception
        self.assertEqual(self.default_product, exc.product)
        self.assertEqual('testcat1', exc.category)
        self.assertEqual('panel1', exc.page)
        self.assertEqual('some/path', exc.path_info)
        self.assertEqual(self.PRODUCT_PANELS_ALLOWED, exc.admin_panels)

    def test_productadmin_product_panel_blacklist(self):
        """Test blacklisted admin panel with PRODUCT_ADMIN in product env
        """
        req = self.req
        req.authname = 'prodadmin'
        req.environ['PATH_INFO'] = '/admin/testcat3/panel1/some/path'
        with self.assertRaises(HTTPNotFound):
            self._dispatch(req, self.env)

    def test_productadmin_product_panel_norules(self):
        """Test unspecified admin panel with PRODUCT_ADMIN in product env
        """
        req = self.req
        req.authname = 'prodadmin'
        req.environ['PATH_INFO'] = '/admin/testcat1/panel2/some/path'
        with self.assertRaises(HTTPNotFound):
            self._dispatch(req, self.env)

    def test_productadmin_product_plugins(self):
        """Plugin admin panel with PRODUCT_ADMIN in product env
        """
        req = self.req
        req.authname = 'prodadmin'
        req.environ['PATH_INFO'] = '/admin/general/plugin'
        with self.assertRaises(HTTPNotFound):
            self._dispatch(req, self.env)

    # Without meta-permissions
    def test_user_global_panel_whitelist(self):
        """Test whitelisted admin panel without meta-perm in product env
        """
        req = self.req
        req.authname = 'testuser'
        req.environ['PATH_INFO'] = '/admin/testcat1/panel1/some/path'
        with self.assertRaises(HTTPNotFound):
            self._dispatch(req, self.global_env)

    def test_user_global_panel_blacklist(self):
        """Test blacklisted admin panel without meta-perm in product env
        """
        req = self.req
        req.authname = 'testuser'
        req.environ['PATH_INFO'] = '/admin/testcat3/panel1/some/path'
        with self.assertRaises(HTTPNotFound):
            self._dispatch(req, self.global_env)

    def test_user_global_panel_norules(self):
        """Test unspecified admin panel without meta-perm in product env
        """
        req = self.req
        req.authname = 'testuser'
        req.environ['PATH_INFO'] = '/admin/testcat1/panel2/some/path'
        with self.assertRaises(HTTPNotFound):
            self._dispatch(req, self.global_env)

    def test_user_global_plugins(self):
        """Plugin admin panel without meta-perm in global env
        """
        req = self.req
        req.authname = 'testuser'
        req.environ['PATH_INFO'] = '/admin/general/plugin'
        with self.assertRaises(HTTPNotFound):
            self._dispatch(req, self.global_env)

    def test_user_product_panel_whitelist(self):
        """Test whitelisted admin panel without meta-perm in product env
        """
        req = self.req
        req.authname = 'testuser'
        req.environ['PATH_INFO'] = '/admin/testcat1/panel1/some/path'
        with self.assertRaises(HTTPNotFound):
            self._dispatch(req, self.env)

    def test_user_product_panel_blacklist(self):
        """Test blacklisted admin panel without meta-perm in product env
        """
        req = self.req
        req.authname = 'testuser'
        req.environ['PATH_INFO'] = '/admin/testcat3/panel1/some/path'
        with self.assertRaises(HTTPNotFound):
            self._dispatch(req, self.env)

    def test_user_product_panel_norules(self):
        """Test unspecified admin panel without meta-perm in product env
        """
        req = self.req
        req.authname = 'testuser'
        req.environ['PATH_INFO'] = '/admin/testcat1/panel2/some/path'
        with self.assertRaises(HTTPNotFound):
            self._dispatch(req, self.env)

    def test_user_product_plugins(self):
        """Plugin admin panel without meta-perm in product env
        """
        req = self.req
        req.authname = 'testuser'
        req.environ['PATH_INFO'] = '/admin/general/plugin'
        with self.assertRaises(HTTPNotFound):
            self._dispatch(req, self.env)



def test_suite():
    return unittest.TestSuite([
            unittest.makeSuite(ProductAdminSetupTestCase,'test'),
            unittest.makeSuite(ProductAdminDispatchTestCase,'test'),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

