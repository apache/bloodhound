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
import shutil

from bhsearch.api import BloodhoundSearchApi, ASC, SortInstruction
from bhsearch.query_parser import DefaultQueryParser
from bhsearch.search_resources.ticket_search import TicketSearchParticipant
from bhsearch.tests import unittest
from bhsearch.tests.base import BaseBloodhoundSearchTest
from bhsearch.whoosh_backend import WhooshBackend


class ApiQueryWithWhooshTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        super(ApiQueryWithWhooshTestCase, self).setUp(create_req=True)
        WhooshBackend(self.env).recreate_index()
        self.search_api = BloodhoundSearchApi(self.env)
        self.ticket_participant = TicketSearchParticipant(self.env)
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

    def test_that_filter_queries_applied(self):
        #arrange
        self.insert_ticket("t1", status="closed", component = "c1")
        self.insert_ticket("t2", status="closed", component = "c1")
        self.insert_ticket("t3", status="closed",
            component = "NotInFilterCriteria")
        #act
        results = self.search_api.query(
            "*",
            filter= ['status:"closed"', 'component:"c1"'],
            sort= [SortInstruction("id", ASC)]
        )
        self.print_result(results)
        #assert
        self.assertEqual(2, results.hits)
        docs = results.docs
        self.assertEqual("t1", docs[0]["summary"])
        self.assertEqual("t2", docs[1]["summary"])

    def test_that_upgrading_environment_adds_documents_to_index(self):
        self.insert_ticket("t1")
        self.insert_ticket("t2")

        self.search_api.upgrade_environment(self.env.db_transaction)

        results = self.search_api.query("type:ticket")

        self.assertEqual(2, results.hits)

    def test_can_index_wiki_with_same_id_from_different_products(self):
        with self.product('p1'):
            self.insert_wiki('title', 'content')
        with self.product('p2'):
            self.insert_wiki('title', 'content 2')

        results = self.search_api.query("type:wiki")

        self.assertEqual(results.hits, 2)

#TODO: check this later
#    @unittest.skip("Check with Whoosh community")
#    def test_can_search_id_and_summary(self):
#        #arrange
#        self.insert_ticket("summary1")
#        self.insert_ticket("summary2 1")
#        #act
#        results = self.search_api.query("1")
#        self.print_result(results)
#        #assert
#        self.assertEqual(2, results.hits)
#        docs = results.docs
#        self.assertEqual("summary1", docs[0]["summary"])


def suite():
    return unittest.makeSuite(ApiQueryWithWhooshTestCase, 'test')

if __name__ == '__main__':
    unittest.main()
