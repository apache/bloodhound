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

"""Tests for Apache(TM) Bloodhound's admin console in product environments"""

import os.path
import sys
import unittest

from trac.admin.tests.console import TracadminTestCase, load_expected_results

from multiproduct.env import ProductEnvironment
from tests.env import MultiproductTestCase


class ProductTracAdminTestCase(TracadminTestCase, MultiproductTestCase):

    expected_results = load_expected_results(
            os.path.join(os.path.split(__file__)[0], 'console-tests.txt'),
            '===== (test_[^ ]+) =====')

    @property
    def env(self):
        env = getattr(self, '_env', None)
        if env is None:
            self.global_env = self._setup_test_env(
                    enable=('trac.*', 'multiproduct.*'),
                    disable=('trac.tests.*',),
            )
            self._upgrade_mp(self.global_env)
            self._setup_test_log(self.global_env)
            self._load_product_from_data(self.global_env, self.default_product)
            self._env = env = ProductEnvironment(self.global_env,
                                                 self.default_product)
            self._load_default_data(env)
        return env

    @env.setter
    def env(self, value):
        pass

    def tearDown(self):
        self.global_env.reset_db()
        self.global_env = self._env = None

    def test_product_help_ok(self):
        self._admin.env_set('', self.global_env)
        from trac import __version__
        test_name = sys._getframe().f_code.co_name
        expected_results = self.expected_results[test_name] \
                           % {'version': __version__}
        rv, output = self._execute('product admin %s help'
                                   % self.default_product)
        self.assertEqual(0, rv)
        self.assertEqual(expected_results, output)

    def test_product_help_version(self):
        rv, output = self._execute('help version')
        self.assertEqual(0, rv)
        expected = self.expected_results[self._testMethodName]
        self.assertEqual(expected, output)

    def test_product_help_version_add(self):
        rv, output = self._execute('help version add')
        self.assertEqual(0, rv)
        expected = self.expected_results[self._testMethodName]
        self.assertEqual(expected, output)

    def test_product_fail_version_add(self):
        rv, output = self._execute('version add v x y')
        self.assertEqual(2, rv)
        expected = self.expected_results[self._testMethodName]
        self.assertEqual(expected, output)


def test_suite():
    return unittest.TestSuite([
            unittest.makeSuite(ProductTracAdminTestCase),
    ])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
