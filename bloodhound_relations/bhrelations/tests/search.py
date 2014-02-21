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
import tempfile
import unittest

from bhsearch.api import BloodhoundSearchApi

# TODO: Figure how to get trac to load components from these modules
import bhsearch.query_parser, bhsearch.search_resources.ticket_search, \
    bhsearch.whoosh_backend
import bhrelations.search
from bhrelations.tests.base import BaseRelationsTestCase


class SearchIntegrationTestCase(BaseRelationsTestCase):
    def setUp(self):
        BaseRelationsTestCase.setUp(self, enabled=['bhsearch.*'])
        self.global_env.path = tempfile.mkdtemp('bhrelations-tempenv')
        self.search_api = BloodhoundSearchApi(self.env)
        self.search_api.upgrade_environment(self.env.db_transaction)

    def tearDown(self):
        shutil.rmtree(self.env.path)
        BaseRelationsTestCase.tearDown(self)

    def test_relations_are_indexed_on_creation(self):
        t1 = self._insert_and_load_ticket("Foo")
        t2 = self._insert_and_load_ticket("Bar")

        self.relations_system.add(t1, t2, 'dependent')

        result = self.search_api.query('dependent:#2')
        self.assertEqual(result.hits, 1)

    def test_relations_are_indexed_on_deletion(self):
        t1 = self._insert_and_load_ticket("Foo")
        t2 = self._insert_and_load_ticket("Bar")

        self.relations_system.add(t1, t2, 'dependent')
        relations = self.relations_system.get_relations(t1)
        self.relations_system.delete(relations[0]["relation_id"])

        result = self.search_api.query('dependent:#2')
        self.assertEqual(result.hits, 0)

    def test_different_types_of_queries(self):
        t1 = self._insert_and_load_ticket("Foo")
        t2 = self._insert_and_load_ticket("Bar")

        self.relations_system.add(t1, t2, 'dependent')

        self.assertEqual(self.search_api.query('dependent:#2').hits, 1)
        self.assertEqual(self.search_api.query('dependent:#tp1-2').hits, 1)


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(SearchIntegrationTestCase, 'test'))
    return test_suite

if __name__ == '__main__':
    unittest.main()
