# -*- coding: UTF-8 -*-

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

from trac.test import EnvironmentStub
from trac.web.chrome import Chrome

from bhdashboard.web_ui import DashboardModule
from bhtheme.theme import BloodhoundTheme
from bhtheme.tests import unittest


class ThemeTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub(enable=('trac.*', 'bhtheme.*'),
                                   default_data=True)
        self.bhtheme = BloodhoundTheme(self.env)

    def tearDown(self):
        self.env.reset_db()

    def test_templates_dirs(self):
        chrome = Chrome(self.env)
        self.assertFalse(self.env.is_component_enabled(DashboardModule))
        for dir in self.bhtheme.get_templates_dirs():
            self.assertIn(dir, chrome.get_all_templates_dirs())


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ThemeTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
