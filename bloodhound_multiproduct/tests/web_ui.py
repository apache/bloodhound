
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

"""Tests for Apache(TM) Bloodhound's web modules"""

import sys
import unittest
from wsgiref.util import setup_testing_defaults

from trac.core import Component, implements
from trac.perm import PermissionCache, PermissionSystem
from trac.resource import ResourceNotFound
from trac.web.api import HTTPInternalError, HTTPNotFound, IRequestFilter, \
                         Request, RequestDone
from trac.web.href import Href
from trac.web.main import RequestDispatcher

from multiproduct.api import MultiProductSystem
from multiproduct.env import ProductEnvironment
from multiproduct.model import Product
from multiproduct.web_ui import ProductModule
from multiproduct.hooks import ProductRequestWithSession

from tests.env import MultiproductTestCase

#----------------
# Testing infrastructure for request handlers
#----------------

class TestRequestSpy(Component):

    implements(IRequestFilter)

    def testMatch(self, req, handler):
        raise AssertionError('Test setup error: Missing match assertions')

    def testProcessing(self, req, template, data, content_type):
        raise AssertionError('Test setup error: Missing processing assertions')

    # IRequestFilter methods
    def pre_process_request(self, req, handler):
        self.testMatch(req, handler)
        return handler

    def post_process_request(self, req, template, data, content_type):
        self.testProcessing(req, template, data, content_type)
        return template, data, content_type


class RequestHandlerTestCase(MultiproductTestCase):
    """Helper functions to write test cases for request handlers.

    May be used as a mixin class.
    """
    http_status = None
    http_headers = None
    http_body = None
    record_response = False

    def _get_request_obj(self, env):
        environ = {}
        setup_testing_defaults(environ)
        environ['SCRIPT_NAME'] = env.href()

        def start_response(status, headers):
            if self.record_response:
                self.http_status = status
                self.http_headers = dict(headers)
                self.http_body = []
                return lambda body: self.http_body.append(body)
            else:
                return lambda body: None

        req = ProductRequestWithSession(env, environ, start_response)
        return req

    def _dispatch(self, req, env):
        req.perm = PermissionCache(env, req.authname)
        return RequestDispatcher(env).dispatch(req)

    def assertHttpHeaders(self, expectedHeaders):
        for h, v in expectedHeaders.iteritems():
            self.assertTrue(h in self.http_headers, 
                            "Expected HTTP header '%s' not set" % (h,))
            self.assertEquals(v, self.http_headers[h], 
                              "Unexpected value for HTTP header '%s'" % (h,))

    def assertRedirect(self, req, url, permanent=False):
        if permanent:
            self.assertEquals('301 Moved Permanently', self.http_status, 
                              'Unexpected status code in HTTP redirect')
        elif req.method == 'POST':
            self.assertEquals('303 See Other', self.http_status, 
                              'Unexpected status code in HTTP redirect')
        else:
            self.assertEquals('302 Found', self.http_status, 
                              'Unexpected status code in HTTP redirect')
        self.assertHttpHeaders({'Location' : url, 
                                'Content-Type' : 'text/plain', 
                                'Content-Length' : '0',
                                'Pragma' : 'no-cache', 
                                'Cache-Control' : 'no-cache', 
                                'Expires' : 'Fri, 01 Jan 1999 00:00:00 GMT'})


#----------------
# Testing product module
#----------------

class ProductModuleTestCase(RequestHandlerTestCase):
    def setUp(self):
        self._mp_setup()
        self.global_env = self.env
        self.env = ProductEnvironment(self.global_env, self.default_product)

        self.global_env.enable_component(TestRequestSpy)
        self.env.enable_component(TestRequestSpy)
        TestRequestSpy(self.global_env).testMatch = self._assert_product_match
        PermissionSystem(self.global_env).grant_permission('testuser', 'PRODUCT_CREATE')
        PermissionSystem(self.global_env).grant_permission('testuser', 'PRODUCT_VIEW')
        PermissionSystem(self.global_env).grant_permission('testuser', 'PRODUCT_MODIFY')

    def tearDown(self):
        self.global_env.reset_db()
        self.env = self.global_env = None

    expectedPrefix = None
    expectedPathInfo = None

    def _assert_product_match(self, req, handler):
        self.assertIs(ProductModule(self.global_env), handler)
        self.assertEqual(self.expectedPrefix, req.args['productid'],
                         "Unexpected product prefix")
        self.assertEqual(self.expectedPathInfo, req.args['pathinfo'],
                         "Unexpected sub path")

    def test_product_list(self):
        spy = self.global_env[TestRequestSpy]
        self.assertIsNot(None, spy)

        req = self._get_request_obj(self.global_env)
        req.authname = 'testuser'
        req.environ['PATH_INFO'] = '/products'

        mps = MultiProductSystem(self.global_env)
        def assert_product_list(req, template, data, content_type):
            self.assertEquals('product_list.html', template)
            self.assertIs(None, content_type)
            self.assertEquals([mps.default_product_prefix,
                               self.default_product],
                              [p.prefix for p in data.get('products')])
            self.assertTrue('context' in data)
            ctx = data['context']
            self.assertEquals('product', ctx.resource.realm)
            self.assertEquals(None, ctx.resource.id)

        spy.testProcessing = assert_product_list
        with self.assertRaises(RequestDone):
            self._dispatch(req, self.global_env)

    def test_product_new(self):
        spy = self.global_env[TestRequestSpy]
        self.assertIsNot(None, spy)

        req = self._get_request_obj(self.global_env)
        req.authname = 'testuser'
        req.environ['PATH_INFO'] = '/products'
        req.environ['QUERY_STRING'] = 'action=new'

        def assert_product_new(req, template, data, content_type):
            self.assertEquals('product_edit.html', template)
            self.assertIs(None, content_type)
            self.assertFalse('products' in data)
            self.assertTrue('context' in data)
            ctx = data['context']
            self.assertEquals('product', ctx.resource.realm)
            self.assertEquals(None, ctx.resource.id)

        spy.testProcessing = assert_product_new
        with self.assertRaises(RequestDone):
            self._dispatch(req, self.global_env)

    def test_product_view(self):
        spy = self.global_env[TestRequestSpy]
        self.assertIsNot(None, spy)

        def assert_product_view(req, template, data, content_type):
            self.assertEquals('product_view.html', template)
            self.assertIs(None, content_type)
            self.assertFalse('products' in data)

            self.assertTrue('context' in data)
            ctx = data['context']
            self.assertEquals('product', ctx.resource.realm)
            self.assertEquals(real_prefix, ctx.resource.id)

            self.assertTrue('product' in data)
            self.assertEquals(real_prefix, data['product'].prefix)

        spy.testProcessing = assert_product_view

        # Existing product
        req = self._get_request_obj(self.global_env)
        req.authname = 'testuser'
        req.environ['PATH_INFO'] = '/products/%s' % (self.default_product,)

        real_prefix = self.default_product
        self.expectedPrefix = self.default_product
        self.expectedPathInfo = ''
        with self.assertRaises(RequestDone):
            self._dispatch(req, self.global_env)

    def test_missing_product(self):
        spy = self.global_env[TestRequestSpy]
        self.assertIsNot(None, spy)

        mps = MultiProductSystem(self.global_env)
        def assert_product_list(req, template, data, content_type):
            self.assertEquals('product_list.html', template)
            self.assertIs(None, content_type)
            self.assertEquals([mps.default_product_prefix,
                               self.default_product],
                              [p.prefix for p in data.get('products')])
            self.assertTrue('context' in data)
            ctx = data['context']
            self.assertEquals('product', ctx.resource.realm)
            self.assertEquals(None, ctx.resource.id)

        spy.testProcessing = assert_product_list

        # Missing product
        req = self._get_request_obj(self.global_env)
        req.authname = 'testuser'
        req.environ['PATH_INFO'] = '/products/missing'

        self.expectedPrefix = 'missing'
        self.expectedPathInfo = ''
        with self.assertRaises(RequestDone):
            self._dispatch(req, self.global_env)
        self.assertEqual(1, len(req.chrome['warnings']))
        self.assertEqual('Product missing not found',
                         req.chrome['warnings'][0].unescape())

    def test_product_edit(self):
        spy = self.global_env[TestRequestSpy]
        self.assertIsNot(None, spy)

        # HTTP GET
        req = self._get_request_obj(self.global_env)
        req.authname = 'testuser'
        req.environ['PATH_INFO'] = '/products/%s' % (self.default_product,)
        req.environ['QUERY_STRING'] = 'action=edit'

        real_prefix = self.default_product

        def assert_product_edit(req, template, data, content_type):
            self.assertEquals('product_edit.html', template)
            self.assertIs(None, content_type)
            self.assertFalse('products' in data)

            self.assertTrue('context' in data)
            ctx = data['context']
            self.assertEquals('product', ctx.resource.realm)
            self.assertEquals(real_prefix, ctx.resource.id)

            self.assertTrue('product' in data)
            self.assertEquals(real_prefix, data['product'].prefix)

        spy.testProcessing = assert_product_edit

        self.expectedPrefix = self.default_product
        self.expectedPathInfo = ''
        with self.assertRaises(RequestDone):
            self._dispatch(req, self.global_env)

        # HTTP POST
        req = self._get_request_obj(self.global_env)
        req.authname = 'testuser'
        req.environ['REQUEST_METHOD'] = 'POST'
        req.environ['PATH_INFO'] = '/products/%s' % (self.default_product,)
        req.args = dict(action='edit', description='New description',
                        prefix=self.default_product, 
                        name=self.env.product.name)

        spy.testProcessing = assert_product_edit

        self.expectedPrefix = self.default_product
        self.expectedPathInfo = ''
        self.record_response = True
        with self.assertRaises(RequestDone):
            self._dispatch(req, self.global_env)

        try:
            product = Product(self.global_env, 
                              {'prefix' : self.env.product.prefix})
        except ResourceNotFound:
            self.fail('Default test product deleted ?')
        else:
            self.assertEquals('New description', product.description)

        product_url = Href(req.base_path).products(self.default_product)
        self.assertRedirect(req, product_url)

    def test_product_delete(self):
        spy = self.global_env[TestRequestSpy]
        self.assertIsNot(None, spy)

        req = self._get_request_obj(self.global_env)
        req.authname = 'testuser'
        req.environ['PATH_INFO'] = '/products/%s' % (self.default_product,)
        req.environ['QUERY_STRING'] = 'action=delete'
        self.expectedPrefix = self.default_product
        self.expectedPathInfo = ''
        spy.testProcessing = lambda *args, **kwargs: None

        with self.assertRaises(HTTPInternalError) as test_cm:
            self._dispatch(req, self.global_env)

        self.assertEqual('500 Trac Error (Product removal is not allowed!)',
                         unicode(test_cm.exception))


def test_suite():
    return unittest.TestSuite([
            unittest.makeSuite(ProductModuleTestCase,'test'),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

