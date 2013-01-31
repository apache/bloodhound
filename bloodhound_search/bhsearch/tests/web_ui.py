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
import tempfile
import shutil

from urllib import urlencode, unquote

from bhsearch.tests.utils import BaseBloodhoundSearchTest
from bhsearch.web_ui import RequestParameters
from bhsearch.whoosh_backend import WhooshBackend

from trac.test import EnvironmentStub, Mock, MockPerm
from trac.ticket import Ticket
from trac.util.datefmt import FixedOffset
from trac.util import format_datetime
from trac.web import Href, arg_list_to_args, parse_arg_list, RequestDone

BASE_PATH = "/main/"
BHSEARCH_URL = BASE_PATH + "bhsearch"
DEFAULT_DOCS_PER_PAGE = 10

class WebUiTestCaseWithWhoosh(BaseBloodhoundSearchTest):
    def setUp(self):
        self.env = EnvironmentStub(enable=['trac.*', 'bhsearch.*'])
        self.env.path = tempfile.mkdtemp('bhsearch-tempenv')

        whoosh_backend = WhooshBackend(self.env)
        whoosh_backend.recreate_index()

        self.req = Mock(
            perm=MockPerm(),
            chrome={'logo': {}},
            href=Href("/main"),
            base_path=BASE_PATH,
            args=arg_list_to_args([]),
            redirect=self.redirect
        )

        self.redirect_url = None
        self.redirect_permanent = None

    def redirect(self, url, permanent=False):
        self.redirect_url = url
        self.redirect_permanent = permanent
        raise RequestDone

    def tearDown(self):
        shutil.rmtree(self.env.path)
        self.env.reset_db()

    def test_can_process_empty_request(self):
        data = self.process_request()
        self.assertEqual("", data["query"])

    def test_can_process_query_empty_data(self):
        self.req.args[RequestParameters.QUERY] = "bla"
        data = self.process_request()
        self.assertEqual("bla", data["query"])
        self.assertEqual([], data["results"].items)

    def test_can_process_first_page(self):
        self._insert_tickets(5)
        self.req.args[RequestParameters.QUERY] = "summary:test"
        data = self.process_request()
        self.assertEqual("summary:test", data["query"])
        self.assertEqual(5, len(data["results"].items))

    def test_can_return_utc_time(self):
        #arrange
        ticket_id = self.insert_ticket("bla")
        ticket = Ticket(self.env, ticket_id)
        ticket_time = ticket.time_changed
        #act
        self.req.args[RequestParameters.QUERY] = "*:*"
        data = self.process_request()
        result_items = data["results"].items
        #assert
        self.assertEqual(1, len(result_items))
        result_datetime = result_items[0]["date"]
        print "Ticket time: %s, Returned time: %s" % (
            ticket_time,
            result_datetime)
        self.assertEqual(format_datetime(ticket_time), result_items[0]["date"])

    def test_can_return_user_time(self):
        #arrange
        ticket_id = self.insert_ticket("bla")
        ticket = Ticket(self.env, ticket_id)
        ticket_time = ticket.time_changed
        #act
        self.req.tz = FixedOffset(60, 'GMT +1:00')
        self.req.args[RequestParameters.QUERY] = "*:*"
        data = self.process_request()
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
        data = self.process_request()
        docs = data["results"].items
        self.assertEqual(1, len(docs))
        self.assertEqual("/main/ticket/1", docs[0]["href"])

    def test_page_href(self):
        self._insert_tickets(DEFAULT_DOCS_PER_PAGE+1)
        self.req.args[RequestParameters.QUERY] = "*:*"
        data = self.process_request()
        shown_pages =  data["results"].shown_pages
        second_page_href = shown_pages[1]["href"]
        self.assertIn("page=2", second_page_href)
        self.assertIn("q=*%3A*", second_page_href)

    def test_can_apply_type_parameter(self):
        #arrange
        self.insert_ticket("summary1 keyword", status="closed")
        self.insert_ticket("summary2 keyword", status="new")
        self.insert_wiki("dummyTitle", "Some text")
        self.req.args[RequestParameters.QUERY] = "*"
        self.req.args[RequestParameters.TYPE] = "ticket"
        #act
        data = self.process_request()
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
        data = self.process_request()
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
        data = self.process_request()
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
        data = self.process_request()
        #assert
        resource_types =  data["types"]

        all = resource_types[0]
        self.assertNotIn("page=2", all["href"])

        ticket = resource_types[1]
        self.assertNotIn("page=", ticket["href"])

    def test_that_there_are_filters_in_type_links(self):
        #arrange
#        self._insert_tickets(2)
        #act
        self.req.args[RequestParameters.QUERY] = "*"
        self.req.args[RequestParameters.TYPE] = "ticket"
        self.req.args[RequestParameters.FILTER_QUERY] = "status:new"
        data = self.process_request()
        #assert
        for type in data["types"]:
            self.assertNotIn("fq=", type["href"])

    def test_that_type_facet_is_in_default_search(self):
        #arrange
        self._insert_tickets(2)
        #act
        self.req.args[RequestParameters.QUERY] = "*"
        data = self.process_request()
        #assert
        self.assertEquals(1, len(data["facet_counts"]))

    def test_can_return_facets_counts_for_tickets(self):
        #arrange
        self.insert_ticket("T1", status="new", milestone="m1")
        self.insert_ticket("T2", status="closed")
        #act
        self.req.args[RequestParameters.TYPE] = "ticket"
        self.req.args[RequestParameters.QUERY] = "*"
        data = self.process_request()
        #assert
        facet_counts =  data["facet_counts"]
        status_counts = facet_counts["status"]
        self.assertEquals(1, status_counts["new"]["count"])
        self.assertEquals(1, status_counts["closed"]["count"])

    def test_can_create_href_for_facet_counts(self):
        #arrange
        self.insert_ticket("T1", status="new")
        self.insert_ticket("T2", status="closed")
        #act
        self.req.args[RequestParameters.TYPE] = "ticket"
        self.req.args[RequestParameters.QUERY] = "*"
        data = self.process_request()
        #assert
        facet_counts =  data["facet_counts"]
        status_counts = facet_counts["status"]
        self.assertEquals(1, status_counts["new"]["count"])
        self.assertIn("fq=status%3A%22new%22", status_counts["new"]["href"])

    def test_can_handle_none_in_facet_counts(self):
        #arrange
        self.insert_ticket("T1")
        self.insert_ticket("T2")
        #act
        self.req.args[RequestParameters.TYPE] = "ticket"
        self.req.args[RequestParameters.QUERY] = "*"
        data = self.process_request()
        #assert
        facet_counts =  data["facet_counts"]
        status_counts = facet_counts["status"]
        empty_status_count = status_counts[None]
        self.assertEquals(2, empty_status_count["count"])
        self.assertIn(
            'fq=NOT+(status:*)',
            unquote(empty_status_count["href"]))

    def test_can_return_empty_facets_result_for_wiki_pages(self):
        #arrange
        self.insert_wiki("W1","Some text")
        #act
        self.req.args[RequestParameters.TYPE] = "wiki"
        self.req.args[RequestParameters.QUERY] = "*"
        data = self.process_request()
        #assert
        facet_counts =  data["facet_counts"]
        self.assertEquals({}, facet_counts)

    def test_can_accept_multiple_filter_query_parameters(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new")
        self.insert_ticket("T2", component="c1", status="new")
        self.insert_ticket("T3",)
        self._insert_wiki_pages(2)
        #act
        self.req.args[RequestParameters.TYPE] = "ticket"
        self.req.args[RequestParameters.QUERY] = "*"
        self.req.args[RequestParameters.FILTER_QUERY] = [
            'component:"c1"', 'status:"new"']
        data = self.process_request()
        #assert
        page_href = data["page_href"]
        self.assertIn(urlencode({'fq':'component:"c1"'}), page_href)
        self.assertIn(urlencode({'fq':'status:"new"'}), page_href)

        docs = data["results"].items
        self.assertEqual(2, len(docs))


    def test_can_handle_empty_facet_result(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new")
        self.insert_ticket("T2", component="c1", status="new")
        #act
        self.req.args[RequestParameters.TYPE] = "ticket"
        self.req.args[RequestParameters.QUERY] = "*"
        self.req.args[RequestParameters.FILTER_QUERY] = ['component:"c1"']
        data = self.process_request()
        #assert
        facet_counts = data["facet_counts"]

        milestone_facet_count = facet_counts["milestone"]
        print unquote(milestone_facet_count[None]["href"])

    def test_can_handle_multiple_same(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new")
        self.insert_ticket("T2", component="c1", status="new")
        #act
        self.req.args[RequestParameters.TYPE] = "ticket"
        self.req.args[RequestParameters.QUERY] = "*"
        self.req.args[RequestParameters.FILTER_QUERY] = ['component:"c1"']
        data = self.process_request()
        #assert
        facet_counts = data["facet_counts"]

        component_facet_count = facet_counts["component"]
        c1_href = component_facet_count["c1"]["href"]
        print unquote(c1_href)
        self.assertEquals(
            1,
            self._count_parameter_in_url(c1_href, "fq", 'component:"c1"'))

    def test_can_return_current_filter_queries(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new")
        self.insert_ticket("T2", component="c1", status="new")
        #act
        self.req.args[RequestParameters.TYPE] = "ticket"
        self.req.args[RequestParameters.QUERY] = "*"
        self.req.args[RequestParameters.FILTER_QUERY] = [
            'component:"c1"',
            'status:"new"']
        data = self.process_request()
        #assert
        current_filter_queries = data["active_filter_queries"]
        self.assertEquals(2, len(current_filter_queries))

        component_filter =  current_filter_queries[0]
        self.assertEquals('component:"c1"', component_filter["label"])
        self.assertNotIn("fq=", component_filter["href"])

        status_filter =  current_filter_queries[1]
        self.assertEquals('status:"new"', status_filter["label"])
        self.assertIn('fq=component:"c1"', unquote(status_filter["href"]))
        self.assertNotIn('fq=status:"new"', unquote(status_filter["href"]))

    def test_can_return_missing_milestone(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new")
        self.insert_ticket("T2", component="c1", status="new", milestone="A")
        #act
        self.req.args[RequestParameters.TYPE] = "ticket"
        self.req.args[RequestParameters.FILTER_QUERY] = ["NOT (milestone:*)"]
        self.req.args[RequestParameters.QUERY] = "*"
        data = self.process_request()
        #assert
        items = data["results"].items
        self.assertEquals(1, len(items))

    def test_can_return_no_results_for_missing_milestone(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new", milestone="A")
        self.insert_ticket("T2", component="c1", status="new", milestone="A")
        #act
        self.req.args[RequestParameters.TYPE] = "ticket"
        self.req.args[RequestParameters.FILTER_QUERY] = ["NOT (milestone:*)"]
        self.req.args[RequestParameters.QUERY] = "*"
        data = self.process_request()
        #assert
        items = data["results"].items
        self.assertEquals(0, len(items))

    def test_that_type_facet_has_href_to_type(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new", milestone="A")
        #act
        self.req.args[RequestParameters.QUERY] = "*"
        data = self.process_request()
        #assert
        ticket_facet_href = data["facet_counts"]["type"]["ticket"]["href"]
        ticket_facet_href = unquote(ticket_facet_href)
        self.assertIn("type=ticket", ticket_facet_href)
        self.assertNotIn("fq=", ticket_facet_href)

    def test_that_there_is_no_quick_jump_on_ordinary_query(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new", milestone="A")
        #act
        self.req.args[RequestParameters.QUERY] = "*"
        data = self.process_request()
        #assert
        self.assertNotIn("quickjump", data)

    def test_can_redirect_on_ticket_id_query(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new", milestone="A")
        #act
        self.req.args[RequestParameters.QUERY] = "#1"
        self.assertRaises(RequestDone, self.process_request)
        #assert
        self.assertEqual('/main/ticket/1', self.redirect_url)

    def test_can_return_quick_jump_data_on_noquickjump(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new", milestone="A")
        #act
        self.req.args[RequestParameters.QUERY] = "#1"
        self.req.args[RequestParameters.NO_QUICK_JUMP] = "1"
        data = self.process_request()
        #assert
        quick_jump_data = data["quickjump"]
        self.assertEqual('T1 (new)', quick_jump_data["description"])
        self.assertEqual('/main/ticket/1', quick_jump_data["href"])

    def _count_parameter_in_url(self, url, parameter_name, value):
        parameter_to_find = (parameter_name, value)
        parsed_parameters = parse_arg_list(url)
        i = 0
        for parameter in parsed_parameters:
            if parameter == parameter_to_find:
                i += 1

        return i

    def _assertResourceType(self, type, label, active, href_contains = None):
        self.assertEquals(label, type["label"])
        self.assertEquals(active, type["active"])
        if href_contains:
            self.assertIn(href_contains, type["href"])

    def _insert_tickets(self, n):
        for i in range(1, n+1):
            self.insert_ticket("test %s" % i)

    def _insert_wiki_pages(self, n):
        for i in range(1, n+1):
            self.insert_wiki("test %s" % i)

def suite():
    return unittest.makeSuite(WebUiTestCaseWithWhoosh, 'test')

if __name__ == '__main__':
    unittest.main()
