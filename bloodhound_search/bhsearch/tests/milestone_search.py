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
import unittest
import tempfile

from bhsearch.api import BloodhoundSearchApi
from bhsearch.search_resources.milestone_search import MilestoneSearchParticipant
from bhsearch.query_parser import DefaultQueryParser
from bhsearch.tests.utils import BaseBloodhoundSearchTest
from bhsearch.whoosh_backend import WhooshBackend

from trac.test import EnvironmentStub
from trac.ticket import Milestone


class MilestoneIndexerEventsTestCase(BaseBloodhoundSearchTest):
    DUMMY_MILESTONE_NAME = "dummyName"

    def setUp(self):
        self.env = EnvironmentStub(enable=['bhsearch.*'])
        self.env.path = tempfile.mkdtemp('bhsearch-tempenv')
        self.env.config.set('bhsearch', 'silence_on_error', "False")
        self.whoosh_backend = WhooshBackend(self.env)
        self.whoosh_backend.recreate_index()
        self.search_api = BloodhoundSearchApi(self.env)
        self.milestone_participant = MilestoneSearchParticipant(self.env)
        self.query_parser = DefaultQueryParser(self.env)

    def tearDown(self):
        shutil.rmtree(self.env.path)
        self.env.reset_db()

    def test_can_index_created_milestone(self):
        #arrange
        self.insert_milestone(self.DUMMY_MILESTONE_NAME, "dummy text")
        #act
        results = self.search_api.query("*:*")
        #assert
        self.print_result(results)
        self.assertEqual(1, results.hits)
        doc = results.docs[0]
        self.assertEqual(self.DUMMY_MILESTONE_NAME, doc["id"])
        self.assertEqual("dummy text", doc["content"])
        self.assertEqual("milestone", doc["type"])
        self.assertNotIn("due", doc )

    def test_can_index_minimal_milestone(self):
        #arrange
        self.insert_milestone(self.DUMMY_MILESTONE_NAME)
        #act
        results = self.search_api.query("*:*")
        #assert
        self.print_result(results)
        self.assertEqual(1, results.hits)
        doc = results.docs[0]
        self.assertEqual(self.DUMMY_MILESTONE_NAME, doc["id"])
        self.assertNotIn("content", doc)


    def test_can_index_renamed_milestone(self):
        #arrange
        self.insert_milestone(self.DUMMY_MILESTONE_NAME, "dummy text")
        self.change_milestone(
            self.DUMMY_MILESTONE_NAME,
            name="updated name",
            description="updated description",
        )
        #act
        results = self.search_api.query("*:*")
        #assert
        self.print_result(results)
        self.assertEqual(1, results.hits)
        doc = results.docs[0]
        self.assertEqual("updated name", doc["id"])
        self.assertEqual("updated description", doc["content"])

    def test_can_index_changed_milestone(self):
        #arrange
        self.insert_milestone(self.DUMMY_MILESTONE_NAME, "dummy text")
        self.change_milestone(
            self.DUMMY_MILESTONE_NAME,
            description="updated description",
        )
        #act
        results = self.search_api.query("*:*")
        #assert
        self.print_result(results)
        self.assertEqual(1, results.hits)
        doc = results.docs[0]
        self.assertEqual(self.DUMMY_MILESTONE_NAME, doc["id"])
        self.assertEqual("updated description", doc["content"])

    def test_can_index_delete(self):
        #arrange
        self.insert_milestone(self.DUMMY_MILESTONE_NAME)
        Milestone(self.env, self.DUMMY_MILESTONE_NAME).delete()
        #act
        results = self.search_api.query("*.*")
        #assert
        self.print_result(results)
        self.assertEqual(0, results.hits)

    def test_can_reindex_minimal_milestone(self):
        #arrange
        self.insert_milestone(self.DUMMY_MILESTONE_NAME)
        self.whoosh_backend.recreate_index()
        #act
        self.search_api.rebuild_index()
        #assert
        results = self.search_api.query("*:*")
        self.print_result(results)
        self.assertEqual(1, results.hits)
        doc = results.docs[0]
        self.assertEqual(self.DUMMY_MILESTONE_NAME, doc["id"])
        self.assertEqual("milestone", doc["type"])


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(MilestoneIndexerEventsTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main()
