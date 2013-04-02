
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

"""Tests for Apache(TM) Bloodhound's attachments in product environments"""

import shutil
import os.path
import unittest

from trac.attachment import Attachment
from trac.test import EnvironmentStub
from trac.tests.attachment import AttachmentTestCase

from multiproduct.env import ProductEnvironment
from tests.env import MultiproductTestCase

class ProductAttachmentTestCase(AttachmentTestCase, MultiproductTestCase):

    def setUp(self):
        try:
            AttachmentTestCase.setUp(self)
        except:
            self.global_env = self.env
            self.tearDown()
            raise
        else:
            self.global_env = global_env = self.env
            self._upgrade_mp(global_env)
            self._setup_test_log(global_env)
            self._load_product_from_data(global_env, self.default_product)
            self.env = ProductEnvironment(global_env, self.default_product)

            # Root folder for default product environment
            self.attachments_dir = os.path.join(self.global_env.path,
                    'products', self.default_product, 'files', 'attachments')

    def tearDown(self):
        if os.path.exists(self.global_env.path):
            shutil.rmtree(self.global_env.path)
        self.env.reset_db()

    def test_product_path_isolation(self):
        product_attachment = Attachment(self.env, 'ticket', '42')
        global_attachment = Attachment(self.global_env, 'ticket', '42')
        global_attachment.filename = product_attachment.filename = 'foo.txt'

        self.assertNotEqual(product_attachment.path, global_attachment.path)

def test_suite():
    return unittest.TestSuite([
            unittest.makeSuite(ProductAttachmentTestCase,'test'),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

