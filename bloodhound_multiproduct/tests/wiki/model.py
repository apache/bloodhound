
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

"""Tests for Apache(TM) Bloodhound's ticket reports in product environments"""

import os.path
import shutil
import tempfile
import unittest

from trac.wiki.tests.model import WikiPageTestCase

from multiproduct.env import ProductEnvironment
from tests.env import MultiproductTestCase

class ProductWikiPageTestCase(WikiPageTestCase, MultiproductTestCase):

    def setUp(self):
        self.global_env = self._setup_test_env(create_folder=True,
                path=os.path.join(tempfile.gettempdir(), 'trac-tempenv') )
        self._upgrade_mp(self.global_env)
        self._setup_test_log(self.global_env)
        self._load_product_from_data(self.global_env, self.default_product)
        self.env = ProductEnvironment(self.global_env, self.default_product)


    def tearDown(self):
        self.global_env.reset_db()
        shutil.rmtree(self.global_env.path)
        self.env = self.global_env = None


def test_suite():
    return unittest.TestSuite([
            unittest.makeSuite(ProductWikiPageTestCase,'test'),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

