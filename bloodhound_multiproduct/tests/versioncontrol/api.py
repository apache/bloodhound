
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

"""Tests for Apache(TM) Bloodhound's repository API in product environments"""

import unittest

from trac.resource import Resource, get_resource_description, get_resource_url
from trac.versioncontrol.api import Repository
from trac.versioncontrol.tests.api import ResourceManagerTestCase

from multiproduct.env import ProductEnvironment
from tests.env import MultiproductTestCase

class ProductResourceManagerTestCase(ResourceManagerTestCase, \
                                     MultiproductTestCase):

    @property
    def env(self):
        env = getattr(self, '_env', None)
        if env is None:
            self.global_env = self._setup_test_env()
            self._upgrade_mp(self.global_env)
            self._setup_test_log(self.global_env)
            self._load_product_from_data(self.global_env, self.default_product)
            self._env = env = ProductEnvironment(
                    self.global_env, self.default_product)
            self._load_default_data(env)
        return env

    @env.setter
    def env(self, value):
        pass

    def tearDown(self):
        self.global_env.reset_db()
        self.global_env = self._env = None

    def test_resource_changeset(self):
        res = Resource('changeset', '42')
        self.assertEqual('Changeset 42', get_resource_description(self.env, res))
        self.assertEqual('/trac.cgi/products/tp1/changeset/42',
                         get_resource_url(self.env, res, self.env.href))

        repo = Resource('repository', 'repo')
        res = Resource('changeset', '42', parent=repo)
        self.assertEqual('Changeset 42 in repo',
                         get_resource_description(self.env, res))
        self.assertEqual('/trac.cgi/products/tp1/changeset/42/repo',
                         get_resource_url(self.env, res, self.env.href))

    def test_resource_source(self):
        res = Resource('source', '/trunk/src')
        self.assertEqual('path /trunk/src',
                         get_resource_description(self.env, res))
        self.assertEqual('/trac.cgi/products/tp1/browser/trunk/src',
                         get_resource_url(self.env, res, self.env.href))

        repo = Resource('repository', 'repo')
        res = Resource('source', '/trunk/src', parent=repo)
        self.assertEqual('path /trunk/src in repo',
                         get_resource_description(self.env, res))
        self.assertEqual('/trac.cgi/products/tp1/browser/repo/trunk/src',
                         get_resource_url(self.env, res, self.env.href))

        repo = Resource('repository', 'repo')
        res = Resource('source', '/trunk/src', version=42, parent=repo)
        self.assertEqual('path /trunk/src@42 in repo',
                         get_resource_description(self.env, res))
        self.assertEqual('/trac.cgi/products/tp1/browser/repo/trunk/src?rev=42',
                         get_resource_url(self.env, res, self.env.href))

    def test_resource_repository(self):
        res = Resource('repository', 'testrepo')
        self.assertEqual('Repository testrepo',
                         get_resource_description(self.env, res))
        self.assertEqual('/trac.cgi/products/tp1/browser/testrepo',
                         get_resource_url(self.env, res, self.env.href))


def test_suite():
    return unittest.TestSuite([
            unittest.makeSuite(ProductResourceManagerTestCase,'test'),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

