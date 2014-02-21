
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

import unittest

from trac.db.tests.api import ParseConnectionStringTestCase, StringsTestCase, ConnectionTestCase, WithTransactionTest

from tests.db.util import ProductEnvMixin

class ProductParseConnectionStringTestCase(ParseConnectionStringTestCase, ProductEnvMixin):
    pass

class ProductStringsTestCase(StringsTestCase, ProductEnvMixin):
    pass

class ProductConnectionTestCase(ConnectionTestCase, ProductEnvMixin):
    pass

class ProductWithTransactionTestCase(WithTransactionTest, ProductEnvMixin):
    pass

def suite():
    suite = unittest.TestSuite([
        unittest.makeSuite(ParseConnectionStringTestCase, 'test'),
        unittest.makeSuite(StringsTestCase, 'test'),
        unittest.makeSuite(ConnectionTestCase, 'test'),
        unittest.makeSuite(WithTransactionTest, 'test'),
        unittest.makeSuite(ProductParseConnectionStringTestCase, 'test'),
        unittest.makeSuite(ProductStringsTestCase, 'test'),
        unittest.makeSuite(ProductConnectionTestCase, 'test'),
        unittest.makeSuite(ProductWithTransactionTestCase, 'test'),
    ])
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
