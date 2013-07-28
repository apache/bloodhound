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

from trac.ticket.model import Component

from bhsearch.api import BloodhoundSearchApi
from bhsearch.search_resources.ticket_search import TicketIndexer
from bhsearch.tests import unittest
from bhsearch.tests.base import BaseBloodhoundSearchTest
from bhsearch.whoosh_backend import WhooshBackend


class TicketIndexerTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        super(TicketIndexerTestCase, self).setUp()
        self.whoosh_backend = WhooshBackend(self.env)
        self.whoosh_backend.recreate_index()
        self.ticket_indexer = TicketIndexer(self.env)
        self.search_api = BloodhoundSearchApi(self.env)
        self.env.config.set('bhsearch', 'silence_on_error', "False")

    def tearDown(self):
        pass

    def test_does_not_raise_exception_by_default(self):
        self.env.config.set('bhsearch', 'silence_on_error', "True")
        self.ticket_indexer.resource_created(None, None)

    def test_raise_exception_if_configured(self):
        self.env.config.set('bhsearch', 'silence_on_error', "False")
        self.assertRaises(
            Exception,
            self.ticket_indexer.resource_created,
            None)

    def test_can_strip_wiki_syntax(self):
        #act
        self.insert_ticket("T1", description=" = Header")
        #assert
        results = self.search_api.query("*:*")
        self.print_result(results)
        self.assertEqual(1, results.hits)
        self.assertEqual("Header", results.docs[0]["content"])

    def test_that_tickets_updated_after_component_renaming(self):
        #arrange
        INITIAL_COMPONENT = "initial_name"
        RENAMED_COMPONENT = "renamed_name"
        component = self._insert_component(INITIAL_COMPONENT)
        self.insert_ticket("T1", component=INITIAL_COMPONENT)
        self.insert_ticket("T2", component=INITIAL_COMPONENT)
        #act
        component.name = RENAMED_COMPONENT
        component.update()
        #arrange
        results = self.search_api.query("*")
        self.print_result(results)
        for doc in results.docs:
            self.assertEqual(RENAMED_COMPONENT, doc["component"])

    def test_that_ticket_updated_after_changing(self):
        #arrange
        ticket = self.insert_ticket("T1", description="some text")
        #act
        CHANGED_SUMMARY = "T1 changed"
        ticket["summary"] = CHANGED_SUMMARY
        ticket.save_changes()
        #arrange
        results = self.search_api.query("*")
        self.print_result(results)
        self.assertEqual(CHANGED_SUMMARY, results.docs[0]["summary"])

    def test_fills_product_field_if_product_is_set(self):
        with self.product('p'):
            self.insert_ticket("T1")

        results = self.search_api.query("*")
        self.assertEqual(results.docs[0]["product"], 'p')

    def test_can_work_if_env_does_not_have_product(self):
        if 'product' in self.env:
            del self.env["product"]

        self.insert_ticket("T1")

        results = self.search_api.query("*")
        self.assertEqual(results.hits, 1)
        self.assertNotIn("product", results.docs[0])

    def _insert_component(self, name):
        component = Component(self.env)
        component.name = name
        component.insert()
        return component

def suite():
    return unittest.makeSuite(TicketIndexerTestCase, 'test')

if __name__ == '__main__':
    unittest.main()
