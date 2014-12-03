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

from trac.tests import functional
from trac.tests.functional.tester import tc

#----------------
# Functional test cases for preferences (rewritten)
#----------------

# TODO: These classes are almost a copycat of Trac's. Beware of license header

class TestPreferences(functional.FunctionalTwillTestCaseSetup):
    def runTest(self):
        """Set preferences for admin user"""
        prefs_url = self._tester.url + "/prefs"
        # [BLOODHOUND] Preferences link removed
        tc.follow('/prefs')
        tc.url(prefs_url)
        tc.notfind('Your preferences have been saved.')
        tc.formvalue('userprefs', 'name', ' System Administrator ')
        tc.formvalue('userprefs', 'email', ' admin@example.com ')
        tc.submit()
        tc.find('Your preferences have been saved.')
        tc.follow('Date & Time')
        tc.url(prefs_url + '/datetime')
        tc.formvalue('userprefs', 'tz', 'GMT -10:00')
        tc.submit()
        tc.find('Your preferences have been saved.')
        tc.follow('General')
        tc.url(prefs_url)
        tc.notfind('Your preferences have been saved.')
        tc.find('value="System Administrator"')
        tc.find(r'value="admin@example\.com"')
        tc.follow('Date & Time')
        tc.url(prefs_url + '/datetime')
        tc.find('GMT -10:00')


class RegressionTestRev5785(functional.FunctionalTwillTestCaseSetup):
    def runTest(self):
        """Test for regression of the fix in r5785"""
        prefs_url = self._tester.url + "/prefs"
        # [BLOODHOUND] Preferences link removed
        tc.follow('/prefs')
        tc.url(prefs_url)
        self._tester.logout()
        self._tester.login('admin')


class RegressionTestTicket5765(functional.FunctionalTwillTestCaseSetup):
    def runTest(self):
        """Test for regression of http://trac.edgewall.org/ticket/5765
        Unable to turn off 'Enable access keys' in Preferences
        """
        self._tester.go_to_front()
        # [BLOODHOUND] Preferences link removed
        tc.follow('/prefs')
        tc.follow('Keyboard Shortcuts')
        tc.formvalue('userprefs', 'accesskeys', True)
        tc.submit()
        tc.find('name="accesskeys".*checked="checked"')
        tc.formvalue('userprefs', 'accesskeys', False)
        tc.submit()
        tc.notfind('name="accesskeys".*checked="checked"')

def trac_functionalSuite(suite=None):
    suite.addTest(TestPreferences())
    suite.addTest(RegressionTestRev5785())
    suite.addTest(RegressionTestTicket5765())


#--------------
# Multiproduct test cases
#--------------



def functionalSuite(suite=None):
    if not suite:
        import tests.functional
        suite = tests.functional.functionalSuite()

    trac_functionalSuite(suite)

    return suite


if __name__ == '__main__':
    import unittest
    unittest.main(defaultTest='functionalSuite')
