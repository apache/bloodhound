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

import unittest

from trac.perm import PermissionSystem
from trac.tests.functional import FunctionalTwillTestCaseSetup, internal_error
from trac.tests.functional.tester import tc

from multiproduct.env import ProductEnvironment
from tests.functional import MultiproductFunctionalTestCase

#----------------
# Functional test cases for admin web UI & CLI
#----------------


class TestAdminProductDefault(MultiproductFunctionalTestCase,
                              FunctionalTwillTestCaseSetup):
    def runTest(self):
        """Admin set default product"""
        name = self._tester.create_product()
        products_url = self._tester.url + '/admin/ticket/products'
        tc.go(products_url)
        tc.formvalue('product_table', 'default', name)
        tc.submit('apply')
        tc.find('type="radio" name="default" value="%s" checked="checked"'
                % name)
        tc.go(self._tester.url + '/newticket')
        tc.find('<option selected="selected" value="%s">%s</option>'
                % (name, name))
        # Test the "Clear default" button
        tc.go(products_url)
        tc.submit('clear', 'product_table')
        tc.notfind('type="radio" name="default" value=".+" checked="checked"')
        tid = self._tester.create_ticket()


class RegressionTestBhTicket667(MultiproductFunctionalTestCase,
                                FunctionalTwillTestCaseSetup):

    def runTest(self):
        """User is redirected to the login page when the page they are
        navigating to is forbidden.
        """
        env = self._testenv.get_trac_environment()
        actions = PermissionSystem(env).get_user_permissions('anonymous')

        # Revoke all permissions for 'anonymous'
        self._testenv._tracadmin('permission', 'remove', 'anonymous', *actions)
        self._testenv.restart()  # TODO: can be removed when #539 is resolved
        try:
            with self._tester.as_user(None):
                tc.go(self._tester.url)
                tc.notfind(internal_error)
                tc.url(self._tester.url + '/login\?referer=%2F$')
        finally:
            self._testenv._tracadmin('permission', 'add', 'anonymous',
                                     *actions)


def functionalSuite(suite=None):
    if not suite:
        import tests.functional
        suite = tests.functional.functionalSuite()

    suite.addTest(TestAdminProductDefault())
    suite.addTest(RegressionTestBhTicket667())
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='functionalSuite')
