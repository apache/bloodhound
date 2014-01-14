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
import uuid

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
        prefix, name, owner = self._tester.admin_create_product(owner='admin')
        products_url = self._tester.url + '/admin/ticket/products'
        tc.go(products_url)
        tc.formvalue('product_table', 'default', prefix)
        tc.submit('apply')
        tc.find('type="radio" name="default" value="%s" checked="checked"'
                % prefix)
        tc.go(self._tester.url + '/newticket')
        tc.find('<option selected="selected" value="%s">%s</option>'
                % (prefix, name))

        # Test the "Clear default" button
        tc.go(products_url)
        tc.submit('clear', 'product_table')
        tc.notfind('type="radio" name="default" value=".+" checked="checked"')


class TestAdminProductRename(MultiproductFunctionalTestCase,
                             FunctionalTwillTestCaseSetup):
    def runTest(self):
        """Rename product from the admin page."""
        prefix, name, owner = self._tester.admin_create_product(owner='admin')
        with self.in_product(prefix) as (testenv, tester):
            t1 = tester.create_ticket()
            t2 = tester.create_ticket()
        new_name = '%s%s' % (name, str(uuid.uuid4()).split('-')[0])

        admin_product_url = self._tester.url + '/admin/ticket/products'
        tc.go(admin_product_url + '/' + prefix)
        tc.formvalue('modprod', 'name', new_name)
        tc.submit('save')
        tc.find("Your changes have been saved")
        tc.find(r'<a href="/admin/ticket/products/%s">%s</a>'
                % (prefix, new_name))

        with self.in_product(prefix) as (testenv, tester):
            tester.go_to_ticket(t1)
            comment = "Product %s renamed to %s" % (name, new_name)
            tc.find(comment)
            tester.go_to_ticket(t2)
            tc.find(comment)


class TestConsoleProductRename(MultiproductFunctionalTestCase,
                               FunctionalTwillTestCaseSetup):
    def runTest(self):
        """Rename product from the console."""
        prefix, name, owner = self._tester.admin_create_product(owner='admin')
        with self.in_product(prefix) as (testenv, tester):
            t1 = tester.create_ticket()
            t2 = tester.create_ticket()
        new_name = '%s%s' % (name, str(uuid.uuid4()).split('-')[0])

        self._testenv._tracadmin('product', 'rename', prefix, new_name)

        with self.in_product(prefix) as (testenv, tester):
            tester.go_to_ticket(t1)
            comment = "Product %s renamed to %s" % (name, new_name)
            tc.find(comment)
            tester.go_to_ticket(t2)
            tc.find(comment)


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
    suite.addTest(TestAdminProductRename())
    suite.addTest(TestConsoleProductRename())
    suite.addTest(RegressionTestBhTicket667())
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='functionalSuite')
