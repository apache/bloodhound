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

from trac.ticket import Milestone

from bhsearch.api import BloodhoundSearchApi
from bhsearch.search_resources.milestone_search import (
    MilestoneSearchParticipant)
from bhsearch.tests import unittest
from bhsearch.tests.base import BaseBloodhoundSearchTest
from bhsearch.whoosh_backend import WhooshBackend


class MilestoneIndexerEventsTestCase(BaseBloodhoundSearchTest):
    DUMMY_MILESTONE_NAME = "dummyName"

    def setUp(self):
        super(MilestoneIndexerEventsTestCase, self).setUp()
        self.whoosh_backend = WhooshBackend(self.env)
        self.whoosh_backend.recreate_index()
        self.search_api = BloodhoundSearchApi(self.env)

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
        results = self.search_api.query("*")
        self.assertEqual(1, results.hits)
        #act
        Milestone(self.env, self.DUMMY_MILESTONE_NAME).delete()
        #assert
        results = self.search_api.query("*")
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

    def test_that_tickets_updated_after_milestone_renaming(self):
        #asser
        INITIAL_MILESTONE = "initial_milestone"
        RENAMED_MILESTONE = "renamed_name"
        milestone = self.insert_milestone(INITIAL_MILESTONE)
        self.insert_ticket("T1", milestone=INITIAL_MILESTONE)
        self.insert_ticket("T2", milestone=INITIAL_MILESTONE)
        #act
        milestone.name = RENAMED_MILESTONE
        milestone.update()
        #assert
        results = self.search_api.query("type:ticket")
        self.print_result(results)
        self.assertEqual(2, results.hits)
        self.assertEqual(RENAMED_MILESTONE, results.docs[0]["milestone"])
        self.assertEqual(RENAMED_MILESTONE, results.docs[1]["milestone"])

    def test_that_tickets_updated_after_milestone_delete_no_retarget(self):
        #asser
        INITIAL_MILESTONE = "initial_milestone"
        milestone = self.insert_milestone(INITIAL_MILESTONE)
        self.insert_ticket("T1", milestone=INITIAL_MILESTONE)
        self.insert_ticket("T2", milestone=INITIAL_MILESTONE)
        #act
        milestone.delete()
        #assert
        results = self.search_api.query("type:ticket")
        self.print_result(results)
        self.assertEqual(2, results.hits)
        self.assertNotIn("milestone", results.docs[0])
        self.assertNotIn("milestone", results.docs[1])

    def test_that_tickets_updated_after_milestone_delete_with_retarget(self):
        #asser
        INITIAL_MILESTONE = "initial_milestone"
        RETARGET_MILESTONE = "retarget_milestone"
        milestone = self.insert_milestone(INITIAL_MILESTONE)
        self.insert_milestone(RETARGET_MILESTONE)
        self.insert_ticket("T1", milestone=INITIAL_MILESTONE)
        self.insert_ticket("T2", milestone=INITIAL_MILESTONE)
        #act
        milestone.delete(retarget_to=RETARGET_MILESTONE)
        #assert
        results = self.search_api.query("type:ticket")
        self.print_result(results)
        self.assertEqual(2, results.hits)
        self.assertEqual(RETARGET_MILESTONE, results.docs[0]["milestone"])
        self.assertEqual(RETARGET_MILESTONE, results.docs[1]["milestone"])

    def test_fills_product_field_if_product_is_set(self):
        with self.product('p'):
            self.insert_milestone("T1")

        results = self.search_api.query("*")
        self.assertEqual(results.docs[0]["product"], 'p')

    def test_can_work_if_env_does_not_have_product(self):
        if 'product' in self.env:
            del self.env["product"]

        self.insert_milestone("T1")

        results = self.search_api.query("*")
        self.assertEqual(results.hits, 1)
        self.assertNotIn("product", results.docs[0])


class MilestoneSearchParticipantTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        super(MilestoneSearchParticipantTestCase, self).setUp()
        self.milestone_search = MilestoneSearchParticipant(self.env)

    def test_can_get_default_grid_fields(self):
        grid_fields = self.milestone_search.get_default_view_fields("grid")
        self.env.log.debug("grid_fields: %s", grid_fields)
        self.assertGreater(len(grid_fields), 0)

    def test_can_get_default_facets(self):
        default_facets = self.milestone_search.get_default_facets()
        self.env.log.debug("default_facets: %s", default_facets)
        self.assertIsNotNone(default_facets)

    def test_can_get_is_grid_view_defaults(self):
        default_grid_fields = self.milestone_search.get_default_view_fields(
            "grid")
        self.env.log.debug("default_grid_fields: %s", default_grid_fields)
        self.assertIsNotNone(default_grid_fields)

def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(
        unittest.makeSuite(MilestoneIndexerEventsTestCase, 'test'))
    test_suite.addTest(
        unittest.makeSuite(MilestoneSearchParticipantTestCase, 'test'))
    return test_suite

if __name__ == '__main__':
    unittest.main()
