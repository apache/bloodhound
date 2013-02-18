
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

"""Tests for Apache(TM) Bloodhound's Pygments renderer in product environments"""

import sys
if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from trac.mimeview.api import Mimeview
from trac.mimeview.pygments import PygmentsRenderer
from trac.mimeview.tests import pygments as test_pygments 
from trac.web.chrome import Chrome

from multiproduct.env import ProductEnvironment
from tests.env import MultiproductTestCase

have_pygments = False

if test_pygments.have_pygments:
    super_class = test_pygments.PygmentsRendererTestCase
else:
    class super_class(object):
        test_empty_content = test_extra_mimetypes = test_newline_content = \
        test_python_hello = test_python_hello_mimeview = \
                lambda self : None

class ProductPygmentsRendererTestCase(super_class, MultiproductTestCase):

    @property
    def env(self):
        env = getattr(self, '_env', None)
        if env is None:
            self.global_env = self._setup_test_env(
                    enable=[Chrome, PygmentsRenderer]
                )
            self._upgrade_mp(self.global_env)
            self._setup_test_log(self.global_env)
            self._load_product_from_data(self.global_env, self.default_product)
            self._env = env = ProductEnvironment(
                    self.global_env, self.default_product)
        return env

    @env.setter
    def env(self, value):
        pass

    def setUp(self):
        test_pygments.PygmentsRendererTestCase.setUp(self)
        self.pygments = Mimeview(self.env).renderers[0]

    def tearDown(self):
        self.global_env.reset_db()
        self.global_env = self._env = None

ProductPygmentsRendererTestCase = unittest.skipUnless(
        test_pygments.have_pygments, 
        'mimeview/tests/pygments (no pygments installed)'
    )(ProductPygmentsRendererTestCase)

def test_suite():
    return unittest.TestSuite([
            unittest.makeSuite(ProductPygmentsRendererTestCase,'test'),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

