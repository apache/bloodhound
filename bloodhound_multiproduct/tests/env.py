
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

import os.path
import shutil
import tempfile
import unittest

from trac.test import EnvironmentStub
from trac.tests.env import EnvironmentTestCase

from multiproduct.api import MultiProductSystem
from multiproduct.env import ProductEnvironment
from multiproduct.model import Product

# FIXME: Subclass TestCase explictly ?
class MultiproductTestCase(unittest.TestCase):
    r"""Mixin providing access to multi-product testing extensions.

    This class serves to the purpose of upgrading existing Trac test cases
    with multi-product super-powers while still providing the foundations
    to create product-specific subclasses.
    """

    # Product data

    default_product = 'tp1'
    MAX_TEST_PRODUCT = 3

    PRODUCT_DATA = dict(
            ['tp' + str(i), {'prefix':'tp' + str(i),
                             'name' : 'test product ' + str(i),
                             'description' : 'desc for tp' + str(i)}]
            for i in xrange(1, MAX_TEST_PRODUCT)
        )

    # Test setup

    def _setup_test_env(self, create_folder=True, path=None):
        r"""Prepare a new test environment . 

        Optionally set its path to a meaningful location (temp folder
        if `path` is `None`).
        """
        self.env = env = EnvironmentStub(enable=['trac.*', 'multiproduct.*'])
        if create_folder:
            if path is None:
                env.path = tempfile.mkdtemp('bh-product-tempenv')
            else:
                env.path = path
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
        config.save()
        env.setup_log()
        env.log.info('%s test case: %s %s',
                '-' * 10, self.id(), '-' * 10)

    def _load_product_from_data(self, env, prefix):
        r"""Ensure test product with prefix is loaded
        """
        # TODO: Use fixtures implemented in #314
        product_data = self.PRODUCT_DATA[prefix]
        product = Product(env)
        product._data.update(product_data)
        product.insert()

    def _upgrade_mp(self, env):
        r"""Apply multi product upgrades
        """
        self.mpsystem = MultiProductSystem(env)
        try:
            self.mpsystem.upgrade_environment(env.db_transaction)
        except OperationalError:
            # table remains but database version is deleted
            pass

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
                self.env = ProductEnvironment(self.global_env, self.default_product)
            except :
                # All tests should fail if anything goes wrong
                self.global_env.log.exception('Error creating product environment')
                self.env = None
        except:
            shutil.rmtree(self.env.path)
            raise

    def tearDown(self):
        # Discard product environment
        self.env = self.global_env

        EnvironmentTestCase.tearDown(self)

def suite():
    return unittest.makeSuite(ProductEnvTestCase,'test')

if __name__ == '__main__':
    unittest.main(defaultTest='suite')

