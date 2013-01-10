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
from pprint import pprint

import unittest
import tempfile
import shutil
from bhsearch.api import BloodhoundSearchApi
from bhsearch.tests.utils import BaseBloodhoundSearchTest
from bhsearch.ticket_search import TicketSearchParticipant
from bhsearch.web_ui import BloodhoundSearchModule, RequestParameters

from bhsearch.whoosh_backend import WhooshBackend
from trac.test import EnvironmentStub, Mock, MockPerm
from trac.ticket.api import TicketSystem
from trac.ticket import Ticket
from trac.util.datefmt import FixedOffset
from trac.util import format_datetime
from trac.web import Href

BHSEARCH_URL = "/main/bhsearch"
DEFAULT_DOCS_PER_PAGE = 10

class WebUiTestCaseWithWhoosh(BaseBloodhoundSearchTest):
    def setUp(self):
        self.env = EnvironmentStub(enable=['bhsearch.*'])
        self.env.path = tempfile.mkdtemp('bhsearch-tempenv')

#        self.perm = PermissionSystem(self.env)
        self.ticket_system = TicketSystem(self.env)
        self.whoosh_backend = WhooshBackend(self.env)
        self.whoosh_backend.recreate_index()
        self.search_api = BloodhoundSearchApi(self.env)
        self.ticket_participant = TicketSearchParticipant(self.env)
        self.ticket_system = TicketSystem(self.env)
        self.web_ui = BloodhoundSearchModule(self.env)

        self.req = Mock(
            perm=MockPerm(),
            chrome={'logo': {}},
            href=Href("/main"),
            args={},
        )

    def tearDown(self):
        shutil.rmtree(self.env.path)
        self.env.reset_db()

    def _process_request(self):
        response = self.web_ui.process_request(self.req)
        url, data, x = response
        print "Received url: %s data:" % url
        pprint(data)
        if data.has_key("results"):
            print "results :"
            pprint(data["results"].__dict__)
        return data

    def test_can_process_empty_request(self):
        data = self._process_request()
        self.assertEqual("", data["query"])

    def test_can_process_query_empty_data(self):
        self.req.args[RequestParameters.QUERY] = "bla"
        data = self._process_request()
        self.assertEqual("bla", data["query"])
        self.assertEqual([], data["results"].items)

    def test_can_process_first_page(self):
        self._insert_tickets(5)
        self.req.args[RequestParameters.QUERY] = "summary:test"
        data = self._process_request()
        self.assertEqual("summary:test", data["query"])
        self.assertEqual(5, len(data["results"].items))

    def test_can_return_utc_time(self):
        #arrange
        ticket_id = self.insert_ticket("bla")
        ticket = Ticket(self.env, ticket_id)
        ticket_time = ticket.time_changed
        #act
        self.req.args[RequestParameters.QUERY] = "*:*"
        data = self._process_request()
        result_items = data["results"].items
        #assert
        self.assertEqual(1, len(result_items))
        result_datetime = result_items[0]["date"]
        print "Ticket time: %s, Returned time: %s" % (ticket_time, result_datetime)
        self.assertEqual(format_datetime(ticket_time), result_items[0]["date"])

    def test_can_return_user_time(self):
        #arrange
        ticket_id = self.insert_ticket("bla")
        ticket = Ticket(self.env, ticket_id)
        ticket_time = ticket.time_changed
        #act
        self.req.tz = FixedOffset(60, 'GMT +1:00')
        self.req.args[RequestParameters.QUERY] = "*:*"
        data = self._process_request()
        result_items = data["results"].items
        #asset
        self.assertEqual(1, len(result_items))
        expected_datetime = format_datetime(ticket_time)
        result_datetime = result_items[0]["date"]
        print "Ticket time: %s, Formatted time: %s ,Returned time: %s" % (
            ticket_time, expected_datetime,result_datetime)
        self.assertEqual(expected_datetime, result_datetime)

    def test_ticket_href(self):
        self._insert_tickets(1)
        self.req.args[RequestParameters.QUERY] = "*:*"
        data = self._process_request()
        docs = data["results"].items
        self.assertEqual(1, len(docs))
        self.assertEqual("/main/ticket/1", docs[0]["href"])

    def test_page_href(self):
        self._insert_tickets(DEFAULT_DOCS_PER_PAGE+1)
        self.req.args[RequestParameters.QUERY] = "*:*"
        data = self._process_request()
        shown_pages =  data["results"].shown_pages
        second_page_href = shown_pages[1]["href"]
        self.assertIn("page=2", second_page_href)
        self.assertIn("q=*%3A*", second_page_href)

    def test_facets_ticket_only(self):
        self.insert_ticket("summary1 keyword", status="closed")
        self.insert_ticket("summary2 keyword", status="new")
        self.req.args[RequestParameters.QUERY] = "*:*"
        data = self._process_request()
        facets =  data["facets"]
        pprint(facets)
        self.assertEqual({'ticket': 2}, facets["type"])

    def test_facets_ticket_and_wiki(self):
        self.insert_ticket("summary1 keyword", status="closed")
        self.insert_ticket("summary2 keyword", status="new")
        self.insert_wiki("dummyTitle", "Some text")
        self.req.args[RequestParameters.QUERY] = "*"
        data = self._process_request()
        facets =  data["facets"]
        pprint(facets)
        self.assertEqual({'ticket': 2, 'wiki': 1}, facets["type"])

    def test_can_apply_type_parameter(self):
        #arrange
        self.insert_ticket("summary1 keyword", status="closed")
        self.insert_ticket("summary2 keyword", status="new")
        self.insert_wiki("dummyTitle", "Some text")
        self.req.args[RequestParameters.QUERY] = "*"
        self.req.args[RequestParameters.TYPE] = "ticket"
        #act
        data = self._process_request()
        docs = data["results"].items
        #assert
        active_type = data["active_type"]
        self.assertEquals("ticket", active_type)

        resource_types = data["types"]

        all = resource_types[0]
        self._assertResourceType(all, "All", False)
        self.assertNotIn("type", all["href"])

        ticket = resource_types[1]
        self._assertResourceType(ticket, "Ticket", True, "type=ticket")

        wiki = resource_types[2]
        self._assertResourceType(wiki, "Wiki", False, "type=wiki")

    def test_type_parameter_in_links(self):
        self._insert_tickets(12)
        self.req.args[RequestParameters.QUERY] = "*"
        self.req.args[RequestParameters.TYPE] = "ticket"
        self.req.args[RequestParameters.PAGELEN] = "4"
        self.req.args[RequestParameters.PAGE] = "2"
        data = self._process_request()
        results = data["results"]
        docs = results.items
        self.assertEquals(4, len(docs))

        next_chrome_link = self.req.chrome['links']['next'][0]["href"]
        self.assertIn('type=ticket', next_chrome_link)
        self.assertIn('page=3', next_chrome_link)

        prev_chrome_link = self.req.chrome['links']['prev'][0]["href"]
        self.assertIn('type=ticket', prev_chrome_link)
        self.assertIn('page=1', prev_chrome_link)

        self.assertIn('type=ticket', data["page_href"])

        for page in results.shown_pages:
            self.assertIn('type=ticket', page["href"])

    def test_type_grouping(self):
        self.req.args[RequestParameters.QUERY] = "*:*"
        data = self._process_request()
        resource_types =  data["types"]

        all = resource_types[0]
        self._assertResourceType(all, "All", True)
        self.assertNotIn("type", all["href"])

        ticket = resource_types[1]
        self._assertResourceType(ticket, "Ticket", False, "type=ticket")

        wiki = resource_types[2]
        self._assertResourceType(wiki, "Wiki", False, "type=wiki")


    def test_that_there_are_no_page_parameters_for_other_types(self):
        #arrange
        self._insert_tickets(12)
        #act
        self.req.args[RequestParameters.QUERY] = "*"
        self.req.args[RequestParameters.PAGELEN] = "4"
        self.req.args[RequestParameters.PAGE] = "2"
        data = self._process_request()
        #assert
        resource_types =  data["types"]

        all = resource_types[0]
        self.assertIn("page=2", all["href"])

        ticket = resource_types[1]
        self.assertNotIn("page=", ticket["href"])


    def _assertResourceType(self, type, label, active, href_contains = None):
        self.assertEquals(label, type["label"])
        self.assertEquals(active, type["active"])
        if href_contains:
            self.assertIn(href_contains, type["href"])

    def _insert_tickets(self, n):
        for i in range(1, n+1):
            self.insert_ticket("test %s" % i)
def suite():
    return unittest.makeSuite(WebUiTestCaseWithWhoosh, 'test')

if __name__ == '__main__':
    unittest.main()
