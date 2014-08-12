# -*- coding: UTF-8 -*-

# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
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

from trac.test import EnvironmentStub, Mock, MockPerm
from trac.util.datefmt import utc
from trac.web.chrome import Chrome

from bhdashboard.web_ui import DashboardModule
from bhtheme.theme import BloodhoundTheme, KeywordSuggestModule, DuplicateTicketSearch, AutocompleteUsers
from bhtheme.tests import unittest

from trac.ticket import Ticket


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

        self.keywords_component = KeywordSuggestModule(self.env)
        self.duplicateTicket_component = DuplicateTicketSearch(self.env)
        self.autocompleteuser_component = AutocompleteUsers(self.env)

        self.req = Mock(href=self.env.href, authname='anonymous', tz=utc,
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

    def test_get_groups(self):

        self.req.args['term'] = 'de'
        test_users = [u'dev']
        self.env.db_transaction.executemany(
            "INSERT INTO permission VALUES (%s,%s)",
            [('dev', 'WIKI_MODIFY'),
             ('dev', 'REPORT_ADMIN'),
             ('admin', 'REPORT_ADMIN')])
        gona=self.env.get_known_users()
        users = self.autocompleteuser_component._get_groups(self.req)
        self.assertEqual(test_users, users)

    def test_get_keywords_string(self):
        test_keywords = ['key1', 'key2', 'key3']

        self._insert_ticket(self.env, 't1', 'key1,key2,key3')
        self._insert_ticket(self.env, 't2', 'key1,key2')
        self._insert_ticket(self.env, 't3', 'key1')
        keywords = self.keywords_component._get_keywords_string(self.req)
        self.assertEqual(test_keywords, keywords)

    def test_terms_to_search_terms_4(self):

        self.req.args['q'] = 'one two three four'
        test_terms = ['one two three four', 'two three four', 'one two three']

        terms = self.duplicateTicket_component._terms_to_search(self.req)
        self.assertEqual(test_terms, terms)

    def test_terms_to_search_terms_3(self):

        self.req.args['q'] = 'one two three'
        test_terms = ['one two three']

        terms = self.duplicateTicket_component._terms_to_search(self.req)
        self.assertEqual(test_terms, terms)

    def test_sql_to_search_single_values(self):

        db = self.env.get_db_cnx()
        columns = ['summary']
        terms = ['one two']
        test_sql = "(summary LIKE %s ESCAPE '/')"
        test_args = tuple(['%one two%'])

        sql, args = self.duplicateTicket_component._sql_to_search(db, columns, terms)
        self.assertEqual(test_sql, sql)
        self.assertEqual(test_args, args)

    def test_sql_to_search(self):

        db = self.env.get_db_cnx()
        columns = ['summary', 'description']
        terms = ['one two', 'one']
        test_sql = "(summary LIKE %s ESCAPE '/'" \
                   " OR description LIKE %s ESCAPE '/')" \
                   " OR (summary LIKE %s ESCAPE '/' OR description LIKE %s ESCAPE '/')"
        test_args = tuple(['%one two%', '%one two%', '%one%', '%one%'])

        sql, args = self.duplicateTicket_component._sql_to_search(db, columns, terms)
        self.assertEqual(test_sql, sql)
        self.assertEqual(test_args, args)

    @classmethod
    def _insert_ticket(cls, env, summary, keywords, **kw):
        """Helper for inserting a ticket into the database"""
        ticket = Ticket(env)
        ticket["summary"] = summary
        ticket["keywords"] = keywords
        for k, v in kw.items():
            ticket[k] = v
        return ticket.insert()

    def _insert_and_load_ticket(self, summary, **kw):
        return Ticket(self.env, self._insert_ticket(self.env, summary, **kw))


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ThemeTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
