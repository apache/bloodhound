
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

"""Tests for Apache(TM) Bloodhound's tickets batch updates 
in product environments"""

import unittest

from trac.perm import PermissionCache
from trac.test import Mock
from trac.ticket.batch import BatchModifyModule
from trac.ticket.tests.batch import BatchModifyTestCase
from trac.ticket.default_workflow import ConfigurableTicketWorkflow
from trac.util.datefmt import utc

from multiproduct.env import ProductEnvironment
from multiproduct.ticket.web_ui import ProductTicketModule
from tests.env import MultiproductTestCase

class ProductBatchModifyTestCase(BatchModifyTestCase, MultiproductTestCase):

    def setUp(self):
        self.global_env = self._setup_test_env(create_folder=False)
        self._upgrade_mp(self.global_env)
        self._setup_test_log(self.global_env)
        self._load_product_from_data(self.global_env, self.default_product)
        self.env = ProductEnvironment(self.global_env, self.default_product)

        self.global_env.enable_component_in_config(self.env, 
                ConfigurableTicketWorkflow)
        self.global_env.enable_component_in_config(self.env, 
                ProductTicketModule)

        self._load_default_data(self.env)

        self.req = Mock(href=self.env.href, authname='anonymous', tz=utc)
        self.req.session = {}
        self.req.perm = PermissionCache(self.env)

    def tearDown(self):
        self.global_env.reset_db()


def test_suite():
    return unittest.TestSuite([
            unittest.makeSuite(ProductBatchModifyTestCase,'test'),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

