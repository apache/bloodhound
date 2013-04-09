
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
from trac.web.api import IRequestFilter, HTTPNotFound, Request
from trac.web.main import RequestDispatcher

from multiproduct.env import ProductEnvironment
from multiproduct.web_ui import ProductModule

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

    May be used as a mixin.
    """
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
        PermissionSystem(self.global_env).grant_permission('testuser', 'PRODUCT_VIEW')

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
 
    def test_product_pathinfo_warning(self):
        spy = self.env[TestRequestSpy]
        self.assertIsNot(None, spy)

        req = self._get_request_obj()
        req.authname = 'testuser'
        req.environ['PATH_INFO'] = '/products/PREFIX/some/path'
        self.expectedPrefix = 'PREFIX'
        self.expectedPathInfo = '/some/path'
        spy.testProcessing = lambda *args, **kwargs: None

        with self.assertRaises(HTTPNotFound) as test_cm:
            self._dispatch(req, self.global_env)

        self.assertEqual('Unable to render product page. Wrong setup ?',
                         test_cm.exception.detail)


def test_suite():
    return unittest.TestSuite([
            unittest.makeSuite(ProductModuleTestCase,'test'),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

