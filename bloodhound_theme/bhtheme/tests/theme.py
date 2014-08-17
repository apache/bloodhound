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

from trac.test import EnvironmentStub, Mock, MockPerm
from trac.util.datefmt import utc
from trac.web.chrome import Chrome
from trac.wiki.model import WikiPage

from bhdashboard.web_ui import DashboardModule
from bhtheme.theme import BloodhoundTheme, BatchCreateTicketsMacro, CreatedTicketsMacro
from bhtheme.tests import unittest


try:
    from babel import Locale

    locale_en = Locale.parse('en_US')
except ImportError:
    locale_en = None


class ThemeTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub(enable=('trac.*', 'bhtheme.*'),
                                   default_data=True)
        self.bhtheme = BloodhoundTheme(self.env)

        self.BatchCreateTicketsMacro = BatchCreateTicketsMacro(self.env)
        self.CreatedTicketsMacro = CreatedTicketsMacro(self.env)

        self.req = Mock(href=self.env.href, authname='anonymous', tz=utc,
                        method='POST',
                        args=dict(action='dummy'),
                        locale=locale_en, lc_time=locale_en,
                        chrome={'warnings': []})
        self.req.perm = MockPerm()

    def tearDown(self):
        self.env.reset_db()

    def test_templates_dirs(self):
        chrome = Chrome(self.env)
        self.assertFalse(self.env.is_component_enabled(DashboardModule))
        for dir in self.bhtheme.get_templates_dirs():
            self.assertIn(dir, chrome.get_all_templates_dirs())

    def test_batch_create(self):
        with self.env.db_transaction as db:
            db("CREATE TABLE bloodhound_product (prefix text,name text,description text,owner text,UNIQUE (prefix,name))")
            db("INSERT INTO bloodhound_product VALUES ('my','product001','test product 001','anonymous')")
        attr = {
            'summary0': u's1',
            'summary1': u's2',
            'summary2': u's3',
            'summary3': u's4',
            'summary4': u's5',
            'priority1': u'critical',
            'priority0': u'blocker',
            'priority3': u'minor',
            'priority2': u'major',
            'priority4': u'trivial',
            'milestone0': u'milestone1',
            'milestone1': u'milestone2',
            'milestone2': u'milestone3',
            'milestone3': u'milestone4',
            'milestone4': u'milestone1',
            'component4': u'component1',
            'product4': u'my',
            'product3': u'my',
            'product2': u'my',
            'product1': u'my',
            'product0': u'my',
            'component1': u'component2',
            'component0': u'component1',
            'component3': u'component2',
            'component2': u'component1',
            'description4': u'd5',
            'description2': u'd3',
            'description3': u'd4',
            'description0': u'd1',
            'description1': u'd2'}

    def test_update_wiki_content(self):

        w = WikiPage(self.env)
        w.name = 'temp_page'
        w.text = 'test the wiki replace function. ie: [[BatchCreateTickets(5)]] replaces with Created Tickets macro.'
        WikiPage.save(w, 'anonymous', 'comment 01', '127.0.0.1')


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ThemeTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
