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

from bhsearch.api import BloodhoundSearchApi
from bhsearch.query_suggestion import SuggestionFields
from bhsearch.tests import unittest
from bhsearch.tests.base import BaseBloodhoundSearchTest
from bhsearch.web_ui import RequestParameters, RequestContext
from bhsearch.whoosh_backend import WhooshBackend


class QuerySuggestionTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        super(QuerySuggestionTestCase, self).setUp(create_req=True)
        self.whoosh_backend = WhooshBackend(self.env)
        self.whoosh_backend.recreate_index()

        self.search_api = BloodhoundSearchApi(self.env)

    def test_fills_suggestion_field(self):
        self.insert_ticket("test")
        self.insert_milestone("test")
        self.insert_wiki("name", "test")

        results = self.search_api.query("%s:test" % SuggestionFields.BASKET)

        self.assertEqual(results.hits, 3)

    def test_provides_suggestions(self):
        self.insert_ticket("test")
        self.req.args[RequestParameters.QUERY] = "tesk"

        data = self.process_request()

        self.assertIn(RequestContext.DATA_QUERY_SUGGESTION, data)
        suggestion = data[RequestContext.DATA_QUERY_SUGGESTION]
        self.assertEqual(suggestion['query'], 'test')
        self.assertIn('q=test', suggestion['href'])

    def test_provides_suggestions_for_multi_term_queries(self):
        self.insert_ticket("another test")
        self.req.args[RequestParameters.QUERY] = "another tesk"

        data = self.process_request()

        suggestion = data[RequestContext.DATA_QUERY_SUGGESTION]
        self.assertEqual(suggestion['query'], 'another test')

    def test_provides_suggestions_for_queries_with_unknown_words(self):
        self.insert_ticket("test")
        self.req.args[RequestParameters.QUERY] = "another tesk"

        data = self.process_request()

        suggestion = data[RequestContext.DATA_QUERY_SUGGESTION]
        self.assertEqual(suggestion['query'], 'another test')

    def test_suggestion_href_contains_used_filters(self):
        self.insert_ticket("test")
        self.req.args[RequestParameters.QUERY] = "tesk"
        self.req.args[RequestParameters.FILTER_QUERY] = ['filter']

        data = self.process_request()

        suggestion = data[RequestContext.DATA_QUERY_SUGGESTION]
        self.assertIn('fq=filter', suggestion['href'])


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(QuerySuggestionTestCase, 'test'))
    return test_suite

if __name__ == '__main__':
    unittest.main()
