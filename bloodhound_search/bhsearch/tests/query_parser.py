#!/usr/bin/env python
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

from trac.test import Mock

from bhsearch.query_parser import DefaultQueryParser
from bhsearch.tests import unittest
from bhsearch.tests.base import BaseBloodhoundSearchTest
from whoosh import query


class MetaKeywordsParsingTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        super(MetaKeywordsParsingTestCase, self).setUp()
        self.parser = DefaultQueryParser(self.env)

    def test_can_parse_keyword_ticket(self):
        parsed_query = self.parser.parse("$ticket")
        self.assertEqual(parsed_query, query.Term('type', 'ticket'))

    def test_can_parse_NOT_keyword_ticket(self):
        parsed_query = self.parser.parse("NOT $ticket")
        self.assertEqual(parsed_query,
                         query.Not(
                             query.Term('type', 'ticket')))

    def test_can_parse_keyword_wiki(self):
        parsed_query = self.parser.parse("$wiki")
        self.assertEqual(parsed_query, query.Term('type', 'wiki'))

    def test_can_parse_keyword_resolved(self):
        parsed_query = self.parser.parse("$resolved")
        self.assertEqual(parsed_query,
                         query.Or([query.Term('status', 'resolved'),
                                   query.Term('status', 'closed')]))

    def test_can_parse_meta_keywords_that_resolve_to_meta_keywords(self):
        parsed_query = self.parser.parse("$unresolved")
        self.assertEqual(parsed_query,
                         query.Not(
                         query.Or([query.Term('status', 'resolved'),
                                   query.Term('status', 'closed')])))

    def test_can_parse_complex_query(self):
        parsed_query = self.parser.parse("content:test $ticket $unresolved")

        self.assertEqual(parsed_query,
                         query.And([
                             query.Term('content', 'test'),
                             query.Term('type', 'ticket'),
                             query.Not(
                                 query.Or([query.Term('status', 'resolved'),
                                           query.Term('status', 'closed')])
                             )
                         ]))

    def test_can_parse_keyword_me(self):
        context = self._mock_context_with_username('username')

        parsed_query = self.parser.parse("author:$me", context)

        self.assertEqual(parsed_query, query.Term('author', 'username'))

    def test_can_parse_keyword_my(self):
        context = self._mock_context_with_username('username')

        parsed_query = self.parser.parse("$my", context)

        self.assertEqual(parsed_query, query.Term('owner', 'username'))

    def _mock_context_with_username(self, username):
        context = Mock(
            req=Mock(
                authname=username
            )
        )
        return context


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(MetaKeywordsParsingTestCase, 'test'))
    return test_suite

if __name__ == '__main__':
    unittest.main()
