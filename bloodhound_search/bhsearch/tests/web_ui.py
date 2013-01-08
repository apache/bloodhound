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
from bhsearch.tests.utils import BaseBloodhoundSearchTest
from bhsearch.ticket_search import TicketSearchParticipant
from bhsearch.web_ui import BloodhoundSearchModule, SEARCH_PERMISSION

from bhsearch.whoosh_backend import WhooshBackend
from trac.test import EnvironmentStub, Mock, MockPerm
from trac.ticket.api import TicketSystem
from trac.ticket import Ticket
from trac.util.datefmt import FixedOffset
from trac.util import format_datetime
from trac.web import Href

BHSEARCH_URL = "/bhsearch"
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
            href=Href("/bhsearch"),
            args={},
        )
#                self.req = Mock(href=self.env.href, authname='anonymous', tz=utc)
#        self.req = Mock(base_path='/trac.cgi', path_info='',
#                        href=Href('/trac.cgi'), chrome={'logo': {}},
#                        abs_href=Href('http://example.org/trac.cgi'),
#                        environ={}, perm=[], authname='-', args={}, tz=None,
#                        locale='', session=None, form_token=None)

#        self.req = Mock(href=self.env.href, abs_href=self.env.abs_href, tz=utc,
#                        perm=MockPerm())
#

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
        self.req.args["q"] = "bla"
        data = self._process_request()
        self.assertEqual("bla", data["query"])
        self.assertEqual([], data["results"].items)

    def test_can_process_first_page(self):
        self._insert_docs(5)
        self.req.args["q"] = "summary:test"
        data = self._process_request()
        self.assertEqual("summary:test", data["query"])
        self.assertEqual(5, len(data["results"].items))

    def test_can_return_utc_time(self):
        #arrange
        ticket_id = self.insert_ticket("bla")
        ticket = Ticket(self.env, ticket_id)
        ticket_time = ticket.time_changed
        #act
        self.req.args["q"] = "*:*"
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
        self.req.args["q"] = "*:*"
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
        self._insert_docs(1)
        self.req.args["q"] = "*:*"
        data = self._process_request()
        docs = data["results"].items
        self.assertEqual(1, len(docs))
        self.assertEqual(BHSEARCH_URL + "/ticket/1", docs[0]["href"])

    def test_page_href(self):
        self._insert_docs(DEFAULT_DOCS_PER_PAGE+1)
        self.req.args["q"] = "*:*"
        data = self._process_request()
        shown_pages =  data["results"].shown_pages
        self.assertEqual(BHSEARCH_URL + "/bhsearch?q=*%3A*&page=2&noquickjump=1", shown_pages[1]["href"])

    def test_facets(self):
        self.insert_ticket("summary1 keyword", status="closed")
        self.insert_ticket("summary2 keyword", status="new")
        self.req.args["q"] = "*:*"
        data = self._process_request()
        facets =  data["facets"]
        pprint(facets)
        self.assertEqual({u'ticket': 2}, facets["type"])


    def _insert_docs(self, n):
        for i in range(1, n+1):
            self.insert_ticket("test %s" % i)
def suite():
    return unittest.makeSuite(WebUiTestCaseWithWhoosh, 'test')

if __name__ == '__main__':
    unittest.main()
