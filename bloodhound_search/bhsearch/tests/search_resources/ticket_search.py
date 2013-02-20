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
import unittest
from bhsearch.api import BloodhoundSearchApi

from bhsearch.tests.base import BaseBloodhoundSearchTest
from bhsearch.search_resources.ticket_search import TicketIndexer

class TicketIndexerTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        super(TicketIndexerTestCase, self).setUp()
        self.ticket_indexer = TicketIndexer(self.env)
        self.search_api = BloodhoundSearchApi(self.env)
        self.env.config.set('bhsearch', 'silence_on_error', "False")

    def tearDown(self):
        pass

    def test_does_not_raise_exception_by_default(self):
        self.env.config.set('bhsearch', 'silence_on_error', "True")
        self.ticket_indexer.ticket_created(None)

    def test_raise_exception_if_configured(self):
        self.env.config.set('bhsearch', 'silence_on_error', "False")
        self.assertRaises(
            Exception,
            self.ticket_indexer.ticket_created,
            None)

    def test_can_strip_wiki_syntax(self):
        #act
        self.insert_ticket("T1", description=" = Header")
        #assert
        results = self.search_api.query("*:*")
        self.print_result(results)
        self.assertEqual(1, results.hits)
        self.assertEqual("Header", results.docs[0]["content"])

def suite():
    return unittest.makeSuite(TicketIndexerTestCase, 'test')

if __name__ == '__main__':
    unittest.main()
