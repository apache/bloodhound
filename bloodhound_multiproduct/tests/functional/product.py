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

from trac.tests.functional import FunctionalTwillTestCaseSetup
from trac.tests.functional.tester import tc

#----------------
# Functional test cases for products
#----------------

class TestNewProduct(FunctionalTwillTestCaseSetup):
    def runTest(self):
        """Setup new product"""
        prefix = self._tester.create_product()
        base_url = self._testenv.get_env_href(prefix=prefix)
        tc.url(base_url())

        tc.follow('Index')
        tc.find('Index by Title')
        tc.find('<a[^>]*>Index by Date')
        pages = ('TitleIndex', 'RecentChanges', 'InterTrac', 'InterWiki')
        for page in pages:
            tc.find('<a[^>]*>%s' % (page,))

        tc.follow('Index by Date')
        tc.find('Index by Date')
        tc.find('<a[^>]*>Index by Title')


def functionalSuite(suite=None):
    if not suite:
        import tests.functional
        suite = tests.functional.functionalSuite()

    suite.addTest(TestNewProduct())
    return suite

if __name__ == '__main__':
    import unittest
    unittest.main(defaultTest='functionalSuite')
