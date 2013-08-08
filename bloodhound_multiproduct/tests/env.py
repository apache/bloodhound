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

"""Tests for Apache(TM) Bloodhound's product environments"""

from inspect import stack
import os.path
import shutil
from sqlite3 import OperationalError
import sys
import tempfile
from types import MethodType

if sys.version_info < (2, 7):
    import unittest2 as unittest
    from unittest2.case import _AssertRaisesContext
else:
    import unittest
    from unittest.case import _AssertRaisesContext

from trac.config import Option
from trac.core import Component, ComponentMeta
from trac.env import Environment
from trac.test import EnvironmentStub, MockPerm
from trac.tests.env import EnvironmentTestCase
from trac.ticket.report import ReportModule
from trac.ticket.web_ui import TicketModule
from trac.util.text import to_unicode
from trac.web.href import Href

from multiproduct.api import MultiProductSystem
from multiproduct.env import ProductEnvironment
from multiproduct.model import Product


class ProductEnvironmentStub(ProductEnvironment):
    r"""A product environment slightly tweaked for testing purposes
    """
    def get_known_users(self, cnx=None):
        return self.known_users


# FIXME: Subclass TestCase explictly ?
class MultiproductTestCase(unittest.TestCase):
    r"""Mixin providing access to multi-product testing extensions.

    This class serves to the purpose of upgrading existing Trac test cases
    with multi-product super-powers while still providing the foundations
    to create product-specific subclasses.
    """

    # unittest2 extensions

    exceptFailureMessage = None

    class _AssertRaisesLoggingContext(_AssertRaisesContext):
        """Add logging capabilities to assertRaises
        """
        def __init__(self, expected, test_case, expected_regexp=None):
            _AssertRaisesContext.__init__(self, expected, test_case,
                                          expected_regexp)
            self.test_case = test_case

        @staticmethod
        def _tb_locals(tb):
            if tb is None:
                # Inspect interpreter stack two levels up
                ns = stack()[2][0].f_locals.copy()
            else:
                # Traceback already in context
                ns = tb.tb_frame.f_locals.copy()
            ns.pop('__builtins__', None)
            return ns

        def __exit__(self, exc_type, exc_value, tb):
            try:
                return _AssertRaisesContext.__exit__(self, exc_type,
                                                     exc_value, tb)
            except self.failureException, exc:
                msg = self.test_case.exceptFailureMessage 
                if msg is not None:
                    standardMsg = str(exc)
                    msg = msg % self._tb_locals(tb)
                    msg = self.test_case._formatMessage(msg, standardMsg)
                    raise self.failureException(msg)
                else:
                    raise
            finally:
                # Clear message placeholder
                self.test_case.exceptFailureMessage = None

    def assertRaises(self, excClass, callableObj=None, *args, **kwargs):
        """Adds logging capabilities on top of unittest2 implementation.
        """
        if callableObj is None:
            return self._AssertRaisesLoggingContext(excClass, self)
        else:
            return unittest.TestCase.assertRaises(self, excClass, callableObj,
                                                  *args, **kwargs)

    # Product data

    default_product = 'tp1'
    MAX_TEST_PRODUCT = 3

    PRODUCT_DATA = {
        'tp1': {
            'prefix': 'tp1',
            'name': 'test product 1',
            'description': 'desc for tp1',
        },
        'tp2': {
            'prefix': 'tp2',
            'name': 'test product 2',
            'description': 'desc for tp2',
        },
        u'xü': {
            'prefix': u'xü',
            'name': 'Non-ASCII chars',
            'description': 'Unicode chars in name',
        },
        u'Überflüssigkeit': {
            'prefix': u'Überflüssigkeit',
            'name': 'Non-ASCII chars (long)',
            'description': 'Long name with unicode chars',
        },
        'Foo Bar': {
            'prefix': 'Foo Bar',
            'name': 'Whitespaces',
            'description': 'Whitespace chars in name',
        },
        'Foo Bar#baz': {
            'prefix': 'Foo Bar#baz',
            'name': 'Non-alphanumeric',
            'description': 'Special chars in name',
        },
        'pl/de': {
            'prefix': 'pl/de',
            'name': 'Path separator',
            'description': 'URL path separator in name',
        },
    }

    # Test setup

    def _setup_test_env(self, create_folder=True, path=None, **kwargs):
        r"""Prepare a new test environment . 

        Optionally set its path to a meaningful location (temp folder
        if `path` is `None`).
        """
        MultiProductSystem.FakePermClass = MockPerm
        kwargs.setdefault('enable', ['trac.*', 'multiproduct.*'])
        self.env = env = EnvironmentStub(**kwargs)
        if create_folder:
            if path is None:
                env.path = tempfile.mkdtemp('bh-product-tempenv')
            else:
                env.path = path
                if not os.path.exists(path):
                    os.mkdir(path)
        return env

    def _setup_test_log(self, env):
        r"""Ensure test product with prefix is loaded
        """
        logdir = tempfile.gettempdir()
        logpath = os.path.join(logdir, 'trac-testing.log')
        config = env.config
        config.set('logging', 'log_file', logpath)
        config.set('logging', 'log_type', 'file')
        config.set('logging', 'log_level', 'DEBUG')

        # Log SQL queries
        config.set('trac', 'debug_sql', True)

        config.save()
        env.setup_log()
        env.log.info('%s test case: %s %s', '-' * 10, self.id(), '-' * 10)

        # Clean-up logger instance and associated handler
        # Otherwise large test suites will only result in ERROR eventually
        # (at least in Unix systems) with messages 
        #
        # TracError: Error reading '/path/to/file', make sure it is readable.
        # error: /path/to/: Too many open files
        self.addCleanup(self._teardown_test_log, env)

    def _teardown_test_log(self, env):
        if env.log and hasattr(env, '_log_handler'):
            env.log.removeHandler(env._log_handler)
            env._log_handler.flush()
            env._log_handler.close()
            del env._log_handler

    @classmethod
    def _load_product_from_data(cls, env, prefix):
        r"""Ensure test product with prefix is loaded
        """
        # TODO: Use fixtures implemented in #314
        product_data = cls.PRODUCT_DATA[prefix]
        prefix = to_unicode(prefix)
        product = Product(env)
        product._data.update(product_data)
        product.insert()

    @classmethod
    def _upgrade_mp(cls, env):
        r"""Apply multi product upgrades
        """
        # Do not break wiki parser ( see #373 )
        env.disable_component(TicketModule)
        env.disable_component(ReportModule)

        mpsystem = MultiProductSystem(env)
        try:
            mpsystem.upgrade_environment(env.db_transaction)
        except OperationalError:
            # Database is upgraded, but database version was deleted.
            # Complete the upgrade by inserting default product.
            mpsystem._insert_default_product(env.db_transaction)
        # assume that the database schema has been upgraded, enable
        # multi-product schema support in environment
        env.enable_multiproduct_schema(True)

    @classmethod
    def _load_default_data(cls, env):
        r"""Initialize environment with default data by respecting
        values set in system table.
        """
        from trac import db_default

        env.log.debug('Loading default data')
        with env.db_transaction as db:
            for table, cols, vals in db_default.get_data(db):
                if table != 'system':
                    db.executemany('INSERT INTO %s (%s) VALUES (%s)'
                                   % (table, ','.join(cols),
                                      ','.join(['%s' for c in cols])), vals)
        env.log.debug('Loaded default data')

    def _mp_setup(self, **kwargs):
        """Shortcut for quick product-aware environment setup.
        """
        self.env = self._setup_test_env(**kwargs)
        self._upgrade_mp(self.env)
        self._setup_test_log(self.env)
        self._load_product_from_data(self.env, self.default_product)


class ProductEnvTestCase(EnvironmentTestCase, MultiproductTestCase):
    r"""Test cases for Trac environments rewritten for product environments
    """

    # Test setup

    def setUp(self):
        r"""Replace Trac environment with product environment
        """
        EnvironmentTestCase.setUp(self)
        try:
            self.global_env = self.env
            self._setup_test_log(self.global_env)
            self._upgrade_mp(self.global_env)
            self._load_product_from_data(self.global_env, self.default_product)
            try:
                self.env = ProductEnvironment(self.global_env,
                                              self.default_product)
            except:
                # All tests should fail if anything goes wrong
                self.global_env.log.exception(
                    'Error creating product environment')
                self.env = None
        except:
            shutil.rmtree(self.env.path)
            raise

    def tearDown(self):
        # Discard product environment
        self.env = self.global_env

        EnvironmentTestCase.tearDown(self)


class ProductEnvApiTestCase(MultiproductTestCase):
    """Assertions for Apache(TM) Bloodhound product-specific extensions in
    [https://issues.apache.org/bloodhound/wiki/Proposals/BEP-0003 BEP 3]
    """
    def setUp(self):
        self._mp_setup()
        self.product_env = ProductEnvironment(self.env, self.default_product)

    def tearDown(self):
        # Release reference to transient environment mock object
        if self.env is not None:
            try:
                self.env.reset_db()
            except OperationalError:
                # "Database not found ...",
                # "OperationalError: no such table: system" or the like
                pass
        self.env = None
        self.product_env = None

    def test_attr_forward_parent(self):
        """Testing env.__getattr__"""
        class EnvironmentAttrSandbox(EnvironmentStub):
            """Limit the impact of class edits so as to avoid race conditions
            """

        self.longMessage = True

        class AttrSuccess(Exception):
            """Exception raised when target method / property is actually
            invoked.
            """

        def property_mock(attrnm, expected_self):
            def assertAttrFwd(instance):
                self.assertIs(instance, expected_self, 
                              "Mismatch in property '%s'" % (attrnm,))
                raise AttrSuccess
            return property(assertAttrFwd)

        self.env.__class__ = EnvironmentAttrSandbox
        try:
            for attrnm in 'system_info_providers secure_cookies ' \
                    'project_admin_trac_url get_system_info get_version ' \
                    'get_templates_dir get_templates_dir get_log_dir ' \
                    'backup'.split(): 
                original = getattr(Environment, attrnm)
                if isinstance(original, MethodType):
                    translation = getattr(self.product_env, attrnm)
                    self.assertIs(translation.im_self, self.env,
                                  "'%s' not bound to global env in product env"
                                  % (attrnm,))
                    self.assertIs(translation.im_func, original.im_func,
                                  "'%s' function differs in product env"
                                  % (attrnm,))
                elif isinstance(original, (property, Option)):
                    # Intercept property access e.g. properties, Option, ...
                    setattr(self.env.__class__, attrnm,
                            property_mock(attrnm, self.env))

                    self.exceptFailureMessage = 'Property %(attrnm)s'
                    with self.assertRaises(AttrSuccess) as cm_test_attr:
                        getattr(self.product_env, attrnm)
                else:
                    self.fail("Environment member %s has unexpected type"
                              % (repr(original),))

        finally:
            self.env.__class__ = EnvironmentStub

        for attrnm in 'component_activated _component_rules ' \
                'enable_component get_known_users get_repository ' \
                '_component_name'.split():
            original = getattr(Environment, attrnm)
            if isinstance(original, MethodType):
                translation = getattr(self.product_env, attrnm)
                self.assertIs(translation.im_self, self.product_env,
                              "'%s' not bound to product env" % (attrnm,))
                self.assertIs(translation.im_func, original.im_func,
                              "'%s' function differs in product env"
                              % (attrnm,))
            elif isinstance(original, property):
                translation = getattr(ProductEnvironment, attrnm)
                self.assertIs(original, translation,
                              "'%s' property differs in product env"
                              % (attrnm,))

    def test_typecheck(self):
        """Testing env.__init__"""
        self._load_product_from_data(self.env, 'tp2')
        with self.assertRaises(TypeError) as cm_test:
            new_env = ProductEnvironment(self.product_env, 'tp2')

        msg = str(cm_test.exception)
        expected_msg = "Initializer must be called with " \
                       "trac.env.Environment instance as first argument " \
                       "(got multiproduct.env.ProductEnvironment instance " \
                       "instead)"
        self.assertEqual(msg, expected_msg)

    def test_component_enable(self):
        """Testing env.is_component_enabled"""
        class C(Component):
            pass
        # Let's pretend this was declared elsewhere
        C.__module__ = 'dummy_module'

        global_env = self.env
        product_env = self.product_env

        def _test_component_enabled(cls):
            cname = global_env._component_name(cls)
            disable_component_in_config = global_env.disable_component_in_config
            enable_component_in_config = global_env.enable_component_in_config

            # cls initially disabled in both envs
            disable_component_in_config(global_env, cls)
            disable_component_in_config(product_env, cls)

            expected_rules = {
                'multiproduct': True,
                'trac': True,
                'trac.db': True,
                cname: False,
            }
            self.assertEquals(expected_rules, global_env._component_rules)
            self.assertEquals(expected_rules, product_env._component_rules)

            self.assertFalse(global_env.is_component_enabled(cls))
            self.assertFalse(product_env.is_component_enabled_local(cls))
            self.assertIs(global_env[cls], None)
            self.assertIs(product_env[cls], None)

            # cls enabled in product env but not in global env
            disable_component_in_config(global_env, cls)
            enable_component_in_config(product_env, cls)

            expected_rules[cname] = False
            self.assertEquals(expected_rules, global_env._component_rules)
            expected_rules[cname] = True
            self.assertEquals(expected_rules, product_env._component_rules)

            self.assertFalse(global_env.is_component_enabled(cls))
            self.assertTrue(product_env.is_component_enabled_local(cls))
            self.assertIs(global_env[cls], None)
            self.assertIs(product_env[cls], None)

            # cls enabled in both envs
            enable_component_in_config(global_env, cls)
            enable_component_in_config(product_env, cls)

            expected_rules[cname] = True
            self.assertEquals(expected_rules, global_env._component_rules)
            expected_rules[cname] = True
            self.assertEquals(expected_rules, product_env._component_rules)

            self.assertTrue(global_env.is_component_enabled(cls))
            self.assertTrue(product_env.is_component_enabled_local(cls))
            self.assertIsNot(global_env[cls], None)
            self.assertIsNot(product_env[cls], None)

            # cls enabled in global env but not in product env
            enable_component_in_config(global_env, cls)
            disable_component_in_config(product_env, cls)

            expected_rules[cname] = True
            self.assertEquals(expected_rules, global_env._component_rules)
            expected_rules[cname] = False
            self.assertEquals(expected_rules, product_env._component_rules)

            self.assertTrue(global_env.is_component_enabled(cls))
            self.assertFalse(product_env.is_component_enabled_local(cls))
            self.assertIsNot(global_env[cls], None)
            self.assertIs(product_env[cls], None)

        # Test the rules against custom , external component
        _test_component_enabled(C)

        for env in (global_env, product_env):
            env.config.remove('components', env._component_name(C))

         # Test the rules against Trac component class
        _test_component_enabled(TicketModule)

        # ComponentMeta._components is shared between multiple tests.
        # Unregister class C as its fake module might break something else.
        ComponentMeta._components.remove(C)

    def test_href_is_lazy(self):
        href = self.product_env.href
        self.assertIs(href, self.product_env.href)

    def test_abs_href_is_lazy(self):
        abs_href = self.product_env.abs_href
        self.assertIs(abs_href, self.product_env.abs_href)

    def test_path_is_lazy(self):
        path = self.product_env.path
        self.assertIs(path, self.product_env.path)

    def test_path(self):
        """Testing env.path"""
        self.assertEqual(self.product_env.path,
                         os.path.join(self.env.path, 'products',
                                      self.default_product))

    def test_env_config_inheritance(self):
        """Testing env.config"""
        global_config = self.env.config
        product_config = self.product_env.config

        # By default inherit global settings ...
        global_config['section'].set('key', 'value1')
        self.assertEquals('value1', global_config['section'].get('key'))
        self.assertEquals('value1', product_config['section'].get('key'))

        # ... but allow for overrides in product scope
        product_config['section'].set('key', 'value2')
        self.assertEquals('value1', global_config['section'].get('key'))
        self.assertEquals('value2', product_config['section'].get('key'))

    def test_parametric_singleton(self):
        self.assertIs(self.product_env, 
                      ProductEnvironment(self.env, self.default_product))

        for prefix in self.PRODUCT_DATA:
            if prefix != self.default_product:
                self._load_product_from_data(self.env, prefix)

        envgen1 = dict([prefix, ProductEnvironment(self.env, prefix)] 
                       for prefix in self.PRODUCT_DATA)
        envgen2 = dict([prefix, ProductEnvironment(self.env, prefix)] 
                       for prefix in self.PRODUCT_DATA)

        for prefix, env1 in envgen1.iteritems():
            self.assertIs(env1, envgen2[prefix], 
                          "Identity check (by prefix) '%s'" % (prefix,))

        for prefix, env1 in envgen1.iteritems():
            self.assertIs(env1, envgen2[prefix], 
                          "Identity check (by prefix) '%s'" % (prefix,))

        def load_product(prefix):
            products = Product.select(self.env, where={'prefix' : prefix})
            if not products:
                raise LookupError('Missing product %s' % (prefix,))
            else:
                return products[0]

        envgen3 = dict([prefix, ProductEnvironment(self.env,
                                                   load_product(prefix))]
                       for prefix in self.PRODUCT_DATA)

        for prefix, env1 in envgen1.iteritems():
            self.assertIs(env1, envgen3[prefix], 
                          "Identity check (by product model) '%s'" % (prefix,))


class ProductEnvHrefTestCase(MultiproductTestCase):
    """Assertions for resolution of product environment's base URL 
    [https://issues.apache.org/bloodhound/wiki/Proposals/BEP-0003 BEP 3]
    """

    def product_base_url(url_template):
        def decorator(f):
            f.product_base_url = url_template
            return f

        return decorator

    def setUp(self):
        self._mp_setup()
        self.env.path = '/path/to/env'
        self.env.abs_href = Href('http://globalenv.com/trac.cgi')
        url_pattern = getattr(getattr(self, self._testMethodName).im_func,
                              'product_base_url', '')
        self.env.config.set('multiproduct', 'product_base_url', url_pattern)
        self.env.config.set('trac', 'base_url', 'http://globalenv.com/trac.cgi')
        self.product_env = ProductEnvironment(self.env, self.default_product)

    def tearDown(self):
        # Release reference to transient environment mock object
        if self.env is not None:
            try:
                self.env.reset_db()
            except OperationalError:
                # "Database not found ...",
                # "OperationalError: no such table: system" or the like
                pass
        self.env = None
        self.product_env = None

    @product_base_url('http://$(prefix)s.domain.tld/')
    def test_href_subdomain(self):
        """Test product sub domain base URL
        """
        self.assertEqual('/', self.product_env.href())
        self.assertEqual('http://tp1.domain.tld', self.product_env.abs_href())

    @product_base_url('/path/to/bloodhound/$(prefix)s')
    def test_href_sibling_paths(self):
        """Test product base URL at sibling paths
        """
        self.assertEqual('/trac.cgi/path/to/bloodhound/tp1',
                         self.product_env.href())
        self.assertEqual('http://globalenv.com/trac.cgi/path/to/bloodhound/tp1',
                         self.product_env.abs_href())

    @product_base_url('/$(envname)s/$(prefix)s')
    def test_href_inherit_sibling_paths(self):
        """Test product base URL at sibling paths inheriting configuration.
        """
        self.assertEqual('/trac.cgi/env/tp1', self.product_env.href())
        self.assertEqual('http://globalenv.com/trac.cgi/env/tp1',
                         self.product_env.abs_href())

    @product_base_url('')
    def test_href_default(self):
        """Test product base URL is to a default
        """
        self.assertEqual('/trac.cgi/products/tp1', self.product_env.href())
        self.assertEqual('http://globalenv.com/trac.cgi/products/tp1',
                         self.product_env.abs_href())

    @product_base_url('/products/$(prefix)s')
    def test_href_embed(self):
        """Test default product base URL /products/prefix
        """
        self.assertEqual('/trac.cgi/products/tp1', self.product_env.href())
        self.assertEqual('http://globalenv.com/trac.cgi/products/tp1',
                         self.product_env.abs_href())

    @product_base_url('http://$(envname)s.tld/bh/$(prefix)s')
    def test_href_complex(self):
        """Test complex product base URL
        """
        self.assertEqual('/bh/tp1', self.product_env.href())
        self.assertEqual('http://env.tld/bh/tp1', self.product_env.abs_href())

    @product_base_url('http://$(prefix)s.$(envname)s.tld/')
    def test_product_href_uses_multiproduct_product_base_url(self):
        """Test that [multiproduct] product_base_url is used to compute
        abs_href for the product environment when [trac] base_url for
        the product environment is an empty string (the default).
        """
        # Global URLs
        self.assertEqual('http://globalenv.com/trac.cgi', self.env.base_url)
        self.assertEqual('/trac.cgi', self.env.href())
        self.assertEqual('http://globalenv.com/trac.cgi', self.env.abs_href())

        # Product URLs
        self.assertEqual('', self.product_env.base_url)
        self.assertEqual('/', self.product_env.href())
        self.assertEqual('http://tp1.env.tld', self.product_env.abs_href())

    @product_base_url('http://$(prefix)s.$(envname)s.tld/')
    def test_product_href_uses_products_base_url(self):
        """Test that [trac] base_url for the product environment is used to
        compute abs_href for the product environment when [trac] base_url
        for the product environment is different than [trac] base_url for
        the global environment.
        """
        self.product_env.config.set('trac', 'base_url', 'http://productenv.com')
        self.product_env.config.save()

        self.assertEqual('http://productenv.com', self.product_env.base_url)
        self.assertEqual('/', self.product_env.href())
        self.assertEqual('http://productenv.com', self.product_env.abs_href())

    @product_base_url('http://$(prefix)s.$(envname)s.tld/')
    def test_product_href_global_and_product_base_urls_same(self):
        """Test that [multiproduct] product_base_url is used to compute
        abs_href for the product environment when [trac] base_url is the same
        for the product and global environment.
        """
        self.product_env.config.set('trac', 'base_url',
                                    self.env.config.get('trac', 'base_url'))
        self.product_env.config.save()

        self.assertEqual('', self.product_env.base_url)
        self.assertEqual('/', self.product_env.href())
        self.assertEqual('http://tp1.env.tld', self.product_env.abs_href())

    product_base_url = staticmethod(product_base_url)


def test_suite():
    return unittest.TestSuite([
        unittest.makeSuite(ProductEnvTestCase, 'test'),
        unittest.makeSuite(ProductEnvApiTestCase, 'test'),
        unittest.makeSuite(ProductEnvHrefTestCase, 'test'),
    ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
