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

from trac.wiki import WikiSystem, WikiPage

from bhsearch.api import BloodhoundSearchApi
from bhsearch.query_parser import DefaultQueryParser
from bhsearch.search_resources.wiki_search import (
    WikiIndexer, WikiSearchParticipant)
from bhsearch.tests import unittest
from bhsearch.tests.base import BaseBloodhoundSearchTest
from bhsearch.whoosh_backend import WhooshBackend


class WikiIndexerSilenceOnExceptionTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        super(WikiIndexerSilenceOnExceptionTestCase, self).setUp()
        self.env.config.set('bhsearch', 'silence_on_error', "True")
        self.wiki_indexer = WikiIndexer(self.env)

    def tearDown(self):
        pass

    def test_does_not_raise_exception_on_add(self):
        self.wiki_indexer.wiki_page_added(None)

    def test_raise_exception_if_configured(self):
        self.env.config.set('bhsearch', 'silence_on_error', "False")
        self.assertRaises(
            Exception,
            self.wiki_indexer.wiki_page_added,
            None)

class WikiIndexerEventsTestCase(BaseBloodhoundSearchTest):
    DUMMY_PAGE_NAME = "dummyName"

    def setUp(self):
        super(WikiIndexerEventsTestCase, self).setUp()
        self.wiki_system = WikiSystem(self.env)
        self.whoosh_backend = WhooshBackend(self.env)
        self.whoosh_backend.recreate_index()
        self.search_api = BloodhoundSearchApi(self.env)
        self.wiki_participant = WikiSearchParticipant(self.env)
        self.query_parser = DefaultQueryParser(self.env)

    def tearDown(self):
        shutil.rmtree(self.env.path)
        self.env.reset_db()

    def test_can_add_new_wiki_page_to_index(self):
        #arrange
        self.insert_wiki(self.DUMMY_PAGE_NAME, "dummy text")
        #act
        results = self.search_api.query("*:*")
        #assert
        self.print_result(results)
        self.assertEqual(1, results.hits)
        doc = results.docs[0]
        self.assertEqual(self.DUMMY_PAGE_NAME, doc["id"])
        self.assertEqual("dummy text", doc["content"])
        self.assertEqual("wiki", doc["type"])

    def test_can_delete_wiki_page_from_index(self):
        #arrange
        self.insert_wiki(self.DUMMY_PAGE_NAME)
        WikiPage(self.env, self.DUMMY_PAGE_NAME).delete()
        #act
        results = self.search_api.query("*.*")
        #assert
        self.print_result(results)
        self.assertEqual(0, results.hits)

    def test_can_index_changed_event(self):
        #arrange
        self.insert_wiki(self.DUMMY_PAGE_NAME, "Text to be changed")
        page = WikiPage(self.env, self.DUMMY_PAGE_NAME)
        page.text = "changed text with keyword"
        page.save("anAuthor", "some comment", "::1")
        #act
        results = self.search_api.query("*:*")
        #assert
        self.print_result(results)
        self.assertEqual(1, results.hits)
        doc = results.docs[0]
        self.assertEqual("changed text with keyword", doc["content"])

    def test_can_index_renamed_event(self):
        #arrange
        self.insert_wiki(self.DUMMY_PAGE_NAME)
        page = WikiPage(self.env, self.DUMMY_PAGE_NAME)
        page.rename("NewPageName")
        #act
        results = self.search_api.query("*:*")
        #assert
        self.print_result(results)
        self.assertEqual(1, results.hits)
        self.assertEqual("NewPageName", results.docs[0]["id"])

    def test_can_index_version_deleted_event(self):
        #arrange
        self.insert_wiki(self.DUMMY_PAGE_NAME, "version1")
        page = WikiPage(self.env, self.DUMMY_PAGE_NAME)
        page.text = "version 2"
        page.save("anAuthor", "some comment", "::1")
        page.delete(version=2)
        #act
        results = self.search_api.query("*:*")
        #assert
        self.print_result(results)
        self.assertEqual(1, results.hits)
        self.assertEqual("version1", results.docs[0]["content"])

    def test_can_strip_wiki_formatting(self):
        #arrange
        self.insert_wiki(self.DUMMY_PAGE_NAME, " = Header")
        #act
        results = self.search_api.query("*:*")
        #assert
        self.print_result(results)
        self.assertEqual(1, results.hits)
        self.assertEqual("Header", results.docs[0]["content"])

    def test_fills_product_field_if_product_is_set(self):
        with self.product('p'):
            self.insert_wiki(self.DUMMY_PAGE_NAME, "content")

        results = self.search_api.query("*")
        self.assertEqual(results.docs[0]["product"], 'p')

    def test_can_work_if_env_does_not_have_product(self):
        if 'product' in self.env:
            del self.env["product"]

        self.insert_wiki(self.DUMMY_PAGE_NAME, "content")

        results = self.search_api.query("*")
        self.assertEqual(results.hits, 1)
        self.assertNotIn("product", results.docs[0])


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(
        WikiIndexerSilenceOnExceptionTestCase, 'test'))
    test_suite.addTest(unittest.makeSuite(WikiIndexerEventsTestCase, 'test'))
    return test_suite

if __name__ == '__main__':
    unittest.main()
