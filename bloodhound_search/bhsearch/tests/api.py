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
from datetime import datetime, timedelta
from pprint import pprint

import unittest
import tempfile
import shutil
from bhsearch.api import BloodhoundSearchApi
from bhsearch.query_parser import DefaultQueryParser
from bhsearch.tests.utils import BaseBloodhoundSearchTest
from bhsearch.ticket_search import TicketSearchParticipant

from bhsearch.whoosh_backend import WhooshBackend
from trac.test import EnvironmentStub, Mock, MockPerm
from trac.ticket.api import TicketSystem


class ApiQueryWithWhooshTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        self.env = EnvironmentStub(enable=['bhsearch.*'])
        self.env.path = tempfile.mkdtemp('bhsearch-tempenv')
        self.ticket_system = TicketSystem(self.env)
        self.whoosh_backend = WhooshBackend(self.env)
        self.whoosh_backend.recreate_index()
        self.search_api = BloodhoundSearchApi(self.env)
        self.ticket_participant = TicketSearchParticipant(self.env)
        self.ticket_system = TicketSystem(self.env)
        self.query_parser = DefaultQueryParser(self.env)

    def tearDown(self):
        shutil.rmtree(self.env.path)
        self.env.reset_db()

    def test_can_search_free_description(self):
        #arrange
        self.insert_ticket("dummy summary", description="aaa keyword bla")
        #act
        results = self.search_api.query("keyword")
        #assert
        self.print_result(results)
        self.assertEqual(1, results.hits)

    def test_can_query_free_summary(self):
        #arrange
        self.insert_ticket("summary1 keyword")
        #act
        results = self.search_api.query("keyword")
        #assert
        self.print_result(results)
        self.assertEqual(1, results.hits)

    def test_can_query_strict_summary(self):
        #arrange
        self.insert_ticket("summary1 keyword")
        self.insert_ticket("summary2", description = "bla keyword")
        #act
        results = self.search_api.query("summary:keyword")
        #assert
        self.print_result(results)
        self.assertEqual(1, results.hits)

    def test_that_summary_hit_is_higher_than_description(self):
        #arrange
        self.insert_ticket("summary1 keyword")
        self.insert_ticket("summary2", description = "bla keyword")
        #act
        results = self.search_api.query("keyword")
        self.print_result(results)
        #assert
        self.assertEqual(2, results.hits)
        docs = results.docs
        self.assertEqual("summary1 keyword", docs[0]["summary"])
        self.assertEqual("summary2", docs[1]["summary"])

    def test_other_conditions_applied(self):
        #arrange
        self.insert_ticket("summary1 keyword", status="closed")
        self.insert_ticket("summary2", description = "bla keyword")
        self.insert_ticket("summary3", status="closed")
        #act
        results = self.search_api.query("keyword status:closed")
        self.print_result(results)
        #assert
        self.assertEqual(1, results.hits)
        docs = results.docs
        self.assertEqual("summary1 keyword", docs[0]["summary"])

    def test_can_search_id_and_summary(self):
        #arrange
        self.insert_ticket("summary1")
        self.insert_ticket("summary2 1")
        #act
        results = self.search_api.query("1")
        self.print_result(results)
        #assert
        self.assertEqual(2, results.hits)
        docs = results.docs
        self.assertEqual("summary1", docs[0]["summary"])

def suite():
    return unittest.makeSuite(ApiQueryWithWhooshTestCase, 'test')

if __name__ == '__main__':
    unittest.main()
