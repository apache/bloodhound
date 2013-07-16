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

from urllib import urlencode, unquote, unquote_plus

from trac.core import TracError
from trac.search.web_ui import SearchModule as TracSearchModule
from trac.test import Mock, MockPerm
from trac.util import format_datetime
from trac.util.datefmt import FixedOffset
from trac.web import Href, RequestDone, arg_list_to_args, parse_arg_list

from bhsearch import web_ui
from bhsearch.api import ASC, DESC, SortInstruction
from bhsearch.tests import unittest
from bhsearch.tests.base import BaseBloodhoundSearchTest
from bhsearch.web_ui import BloodhoundSearchModule, RequestParameters
from bhsearch.whoosh_backend import WhooshBackend

BASE_PATH = "/main/"
BHSEARCH_URL = BASE_PATH + "bhsearch"
DEFAULT_DOCS_PER_PAGE = 10


class WebUiTestCaseWithWhoosh(BaseBloodhoundSearchTest):
    def setUp(self):
        super(WebUiTestCaseWithWhoosh, self).setUp(
            create_req=True,
        )
        self.req.redirect = self.redirect

        whoosh_backend = WhooshBackend(self.env)
        whoosh_backend.recreate_index()

        self.req.redirect = self.redirect
        self.redirect_url = None
        self.redirect_permanent = None

        self.old_product_environment = web_ui.ProductEnvironment
        self._inject_mocked_product_environment()

    def _inject_mocked_product_environment(self):
        class MockProductEnvironment(object):
            def __init__(self, env, product):
                # pylint: disable=unused-argument
                self.product = product

            def href(self, *args):
                return ('/main/products/%s/' % self.product) + '/'.join(args)

        web_ui.ProductEnvironment = MockProductEnvironment

    def tearDown(self):
        web_ui.ProductEnvironment = self.old_product_environment

    def redirect(self, url, permanent=False):
        self.redirect_url = url
        self.redirect_permanent = permanent
        raise RequestDone

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
        ticket = self.insert_ticket("bla")
        ticket_time = ticket.time_changed
        #act
        self.req.args[RequestParameters.QUERY] = "*:*"
        data = self.process_request()
        result_items = data["results"].items
        #assert
        self.assertEqual(1, len(result_items))
        result_datetime = result_items[0]["date"]
        self.env.log.debug(
            "Ticket time: %s, Returned time: %s",
            ticket_time,
            result_datetime)
        self.assertEqual(format_datetime(ticket_time), result_items[0]["date"])

    def test_can_return_user_time(self):
        #arrange
        ticket = self.insert_ticket("bla")
        ticket_time = ticket.time_changed
        #act
        tzinfo = FixedOffset(60, 'GMT +1:00')
        self.req.tz = tzinfo
        self.req.args[RequestParameters.QUERY] = "*:*"
        data = self.process_request()
        result_items = data["results"].items
        #asset
        self.assertEqual(1, len(result_items))
        expected_datetime = format_datetime(ticket_time, tzinfo=tzinfo)
        result_datetime = result_items[0]["date"]
        self.env.log.debug(
            "Ticket time: %s, Formatted time: %s ,Returned time: %s",
            ticket_time, expected_datetime,result_datetime)
        self.assertEqual(expected_datetime, result_datetime)

    def test_ticket_href(self):
        self._insert_tickets(1)
        self.req.args[RequestParameters.QUERY] = "*:*"
        data = self.process_request()
        docs = data["results"].items
        self.assertEqual(1, len(docs))
        self.assertEqual("/main/ticket/1", docs[0]["href"])

    def test_product_ticket_href(self):
        with self.product('xxx'):
            self._insert_tickets(1)
        self.req.args[RequestParameters.QUERY] = "*:*"
        data = self.process_request()
        docs = data["results"].items
        self.assertEqual(1, len(docs))
        self.assertEqual("/main/products/xxx/ticket/1", docs[0]["href"])

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
        extra_search_options = dict(data["extra_search_fields"])
        self.assertEqual("ticket", extra_search_options['type'])

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
        facet_counts = dict(data["facet_counts"])
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
        facet_counts = dict(data["facet_counts"])
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
        facet_counts = dict(data["facet_counts"])
        status_counts = facet_counts["status"]
        empty_status_count = status_counts[None]
        self.assertEquals(2, empty_status_count["count"])
        self.assertIn(
            'fq=NOT+(status:*)',
            unquote(empty_status_count["href"]))

    def test_can_return_empty_facets_result_for_wiki_pages(self):
        #arrange
        self.insert_wiki("W1", "Some text")
        #act
        self.req.args[RequestParameters.TYPE] = "wiki"
        self.req.args[RequestParameters.QUERY] = "*"
        data = self.process_request()
        #assert
        facet_counts = data["facet_counts"]
        self.assertEquals([], facet_counts)

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
        facet_counts = dict(data["facet_counts"])

        milestone_facet_count = facet_counts["milestone"]
        self.env.log.debug(unquote(milestone_facet_count[None]["href"]))

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
        facet_counts = dict(data["facet_counts"])

        component_facet_count = facet_counts["component"]
        c1_href = component_facet_count["c1"]["href"]
        self.env.log.debug(unquote(c1_href))
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
        self.assertEquals(3, len(current_filter_queries))

        type_filter = current_filter_queries[0]
        self.assertEquals('Ticket', type_filter["label"])
        self.assertNotIn("type=", type_filter["href"])
        self.assertNotIn('fq=', unquote(type_filter["href"]))

        component_filter = current_filter_queries[1]
        self.assertEquals('component:"c1"', component_filter["label"])
        self.assertIn('type=ticket', component_filter["href"])
        self.assertNotIn('fq=component:"c1"',
                         unquote(component_filter["href"]))
        self.assertIn('fq=status:"new"', unquote(component_filter["href"]))

        status_filter = current_filter_queries[2]
        self.assertEquals('status:"new"', status_filter["label"])
        self.assertIn('type=ticket', status_filter["href"])
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
        ticket_facet_href = dict(data["facet_counts"])["type"]["ticket"]["href"]
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


    def test_that_ticket_search_can_return_in_grid(self):
        #arrange
        self.env.config.set(
            'bhsearch',
            'ticket_is_grid_view_default',
            'True')
        self.env.config.set(
            'bhsearch',
            'ticket_default_grid_fields',
            'id,status,milestone,component')
        self.insert_ticket("T1", component="c1", status="new", milestone="A")
        #act
        self.req.args[RequestParameters.QUERY] = "*"
        self.req.args[RequestParameters.TYPE] = "ticket"
        self.req.args[RequestParameters.VIEW] = "grid"
        data = self.process_request()
        #assert
        grid_data = data["headers"]
        self.assertIsNotNone(grid_data)
        fields = [column["name"] for column in grid_data]
        self.assertEquals(["id", "status", "milestone", "component"], fields)

    def test_that_grid_is_switched_off_by_default(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new", milestone="A")
        #act
        self.req.args[RequestParameters.QUERY] = "*"
        data = self.process_request()
        #assert
        self.assertNotIn("headers", data)
        self.assertNotIn("view", data)

    def test_that_grid_is_switched_off_by_default_for_ticket(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new", milestone="A")
        #act
        self.req.args[RequestParameters.QUERY] = "*"
        self.req.args[RequestParameters.TYPE] = "ticket"
        data = self.process_request()
        #assert
        self.assertNotIn("headers", data)
        self.assertNotIn("view", data)


    def test_can_returns_all_views(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new", milestone="A")
        #act
        self.req.args[RequestParameters.QUERY] = "*"
        data = self.process_request()
        #assert
        all_views = data["all_views"]
        free_view = all_views[0]
        self.assertTrue(free_view["is_active"])
        self.assertNotIn("view=", free_view["href"])
        grid = all_views[1]
        self.assertFalse(grid["is_active"])
        self.assertIn("view=grid", grid["href"])

    def test_that_active_view_is_not_set_if_not_requested(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new", milestone="A")
        #act
        self.req.args[RequestParameters.QUERY] = "*"
        data = self.process_request()
        #assert
        self.assertNotIn("active_view", data)

    def test_that_active_view_is_set_if_requested(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new", milestone="A")
        #act
        self.req.args[RequestParameters.QUERY] = "*"
        self.req.args[RequestParameters.VIEW] = "grid"
        data = self.process_request()
        #assert
        extra_search_options = dict(data["extra_search_fields"])
        self.assertEqual("grid", extra_search_options["view"])

    def test_can_apply_sorting(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new", milestone="A")
        self.insert_ticket("T2", component="c1", status="new", milestone="B")
        self.insert_ticket("T3", component="c3", status="new", milestone="C")
        #act
        self.req.args[RequestParameters.QUERY] = "*"
        self.req.args[RequestParameters.SORT] = "component, milestone desc"
        data = self.process_request()
        #assert
        api_sort = data["debug"]["api_parameters"]["sort"]
        self.assertEqual(
            [
                SortInstruction("component", ASC),
                SortInstruction("milestone", DESC),
            ],
            api_sort)
        ids = [item["summary"] for item in data["results"].items]
        self.assertEqual(["T2", "T1", "T3"], ids)

    def test_that_title_is_set_for_free_text_view(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new", milestone="A")
        #act
        self.req.args[RequestParameters.QUERY] = "*"
        data = self.process_request()
        #assert
        self.assertIn("title", data["results"].items[0])


    def test_that_grid_header_has_correct_sort_when_default_sorting(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new", milestone="A")
        #act
        self.req.args[RequestParameters.QUERY] = "*"
        self.req.args[RequestParameters.VIEW] = "grid"
        data = self.process_request()
        #assert
        headers = data["headers"]
        id_header = self._find_header(headers, "id")
        self.assertIn("sort=id+asc", id_header["href"])
        self.assertEquals(None, id_header["sort"])

        time_header = self._find_header(headers, "time")
        self.assertIn("sort=time+asc", time_header["href"])
        self.assertEquals(None, time_header["sort"])

    def test_that_grid_header_has_correct_sort_if_acs_sorting(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new", milestone="A")
        #act
        self.req.args[RequestParameters.QUERY] = "*"
        self.req.args[RequestParameters.VIEW] = "grid"
        self.req.args[RequestParameters.SORT] = "id"

        data = self.process_request()
        #assert
        headers = data["headers"]
        id_header = self._find_header(headers, "id")
        self.assertIn("sort=id+desc", id_header["href"])
        self.assertEquals("asc", id_header["sort"])

    def test_that_active_sort_is_set(self):
        #arrange
        self.insert_ticket("T1", component="c1", status="new", milestone="A")
        #act
        self.req.args[RequestParameters.SORT] = "id, time desc"

        data = self.process_request()
        #assert
        extra_search_options = dict(data["extra_search_fields"])
        self.assertEqual("id, time desc", extra_search_options["sort"])

    def test_that_document_summary_contains_highlighted_search_terms(self):
        term = "searchterm"
        long_text = "foo " * 200 + term + " bar" * 100
        self.insert_wiki("Dummy title", long_text)

        self.req.args[RequestParameters.QUERY] = term
        data = self.process_request()

        content = str(data["results"].items[0]["hilited_content"])
        matched_term = '<em>%s</em>' % term
        self.assertIn(matched_term, content)

    def test_that_only_matched_terms_are_highlighted(self):
        term = "search_term"
        self.insert_wiki(term, term)

        self.req.args[RequestParameters.QUERY] = "name:%s" % term
        data = self.process_request()

        title = str(data["results"].items[0]["title"])
        content = str(data["results"].items[0]["content"])
        matched_term = '<em>%s</em>' % term
        self.assertIn(matched_term, title)
        self.assertNotIn(matched_term, content)

    def test_that_matched_terms_in_title_are_highlighted(self):
        term = "search_term"
        self.insert_wiki(term, 'content')
        self.insert_ticket(term)

        self.req.args[RequestParameters.QUERY] = term
        data = self.process_request()

        for row in data["results"].items:
            title = str(row["title"])
            matched_term = '<em>%s</em>' % term
            self.assertIn(matched_term, str(title))

    def test_that_html_tags_are_escaped(self):
        term = "search_term"
        content = '%s <b>%s</b>' % (term, term)
        self.insert_wiki(term, content)

        self.req.args[RequestParameters.QUERY] = "content:%s" % term
        data = self.process_request()

        content = str(data["results"].items[0]["hilited_content"])
        matched_term = '<em>%s</em>' % term
        self.assertIn(matched_term, content)
        self.assertNotIn('<b>', content)
        self.assertIn('&lt;b&gt;', content)

    def test_that_id_is_displayed_even_if_it_doesnt_contain_query_terms(self):
        id, term = "1", "search_term"
        self.insert_ticket(term, id=id)
        self.insert_wiki(id, term)

        self.req.args[RequestParameters.QUERY] =  term
        data = self.process_request()

        for row in data["results"].items:
            title = row["title"]
            self.assertIn(id, str(title))

    def test_that_id_is_highlighted_in_title(self):
        self.insert_ticket("some summary")
        id = "1"
        self.req.args[RequestParameters.QUERY] = id
        data = self.process_request()
        row = data["results"].items[0]
        title = row["title"]
        self.assertIn('<em>%s</em>' % id, str(title))

    def test_that_content_summary_is_trimmed(self):
        content = "foo " * 1000
        self.insert_wiki("title", content)

        data = self.process_request()

        for row in data["results"].items:
            self.assertLess(len(row['content']), 500)
            self.assertLess(len(row['hilited_content']), 500)

    def test_compatibility_with_legacy_search(self):
        self.env.config.set('bhsearch', 'enable_redirect', "True")
        self.req.path_info = '/search'

        self.assertRaises(RequestDone, self.process_request)
        self.assertIn('/bhsearch', self.redirect_url)
        self.assertEqual(self.redirect_permanent, True)

        self.req.args['wiki'] = 'on'
        self.assertRaises(RequestDone, self.process_request)
        redirect_url = unquote_plus(self.redirect_url)
        self.assertIn('/bhsearch', redirect_url)
        self.assertIn('type=wiki', redirect_url)
        self.assertEqual(self.redirect_permanent, True)

        self.req.args['ticket'] = 'on'
        self.assertRaises(RequestDone, self.process_request)
        redirect_url = unquote_plus(self.redirect_url)
        self.assertIn('fq=type:(ticket OR wiki)', redirect_url)
        self.assertIn('/bhsearch', self.redirect_url)
        self.assertEqual(self.redirect_permanent, True)

        self.req.args['milestone'] = 'on'
        self.assertRaises(RequestDone, self.process_request)
        redirect_url = unquote_plus(self.redirect_url)
        self.assertIn('fq=type:(ticket OR wiki OR milestone)', redirect_url)
        self.assertIn('/bhsearch', self.redirect_url)
        self.assertEqual(self.redirect_permanent, True)

        self.req.args['changeset'] = 'on'
        self.assertRaises(RequestDone, self.process_request)
        redirect_url = unquote_plus(self.redirect_url)
        self.assertIn(
            'fq=type:(ticket OR wiki OR milestone OR changeset)', redirect_url)
        self.assertIn('/bhsearch', self.redirect_url)
        self.assertEqual(self.redirect_permanent, True)

    def test_opensearch_integration(self):
        # pylint: disable=unused-variable
        self.req.path_info = '/bhsearch/opensearch'
        bhsearch = BloodhoundSearchModule(self.env)

        url, data, x = bhsearch.process_request(self.req)

        self.assertEqual(url, 'opensearch.xml')

    def test_returns_correct_handler(self):
        bhsearch = BloodhoundSearchModule(self.env)
        tracsearch = self.env[TracSearchModule]

        class PathInfoSetter(object):
            # pylint: disable=incomplete-protocol
            def __setitem__(other, key, value):
                if key == "PATH_INFO":
                    self.req.path_info = value
        self.req.environ = PathInfoSetter()

        self.env.config.set('bhsearch', 'enable_redirect', "True")

        self.req.path_info = '/search'
        self.assertIs(bhsearch.pre_process_request(self.req, tracsearch),
                      bhsearch)

        self.req.path_info = '/bhsearch'
        self.assertIs(bhsearch.pre_process_request(self.req, tracsearch),
                      bhsearch)

        self.env.config.set('bhsearch', 'enable_redirect', "False")
        # With redirect disabled, handler should not be changed.
        self.req.path_info = '/search'
        self.assertIs(bhsearch.pre_process_request(self.req, None),
                      None)

        self.req.path_info = '/bhsearch'
        self.assertIs(bhsearch.pre_process_request(self.req, None),
                      None)

    def test_that_correct_search_handle_is_selected_for_quick_search(self):
        bhsearch = BloodhoundSearchModule(self.env)

        def process_request(path, enable_redirect, is_default):
            # pylint: disable=unused-variable
            self.req.path_info = path
            self.env.config.set('bhsearch', 'enable_redirect',
                                str(enable_redirect))
            self.env.config.set('bhsearch', 'is_default', str(is_default))
            template, data, content_type = \
                bhsearch.post_process_request(self.req, '', {}, '')
            return data

        data = process_request('/', enable_redirect=False, is_default=False)
        self.assertIn('search_handler', data)
        self.assertEqual(data['search_handler'], self.req.href.search())

        data = process_request('/', enable_redirect=True, is_default=False)
        self.assertIn('search_handler', data)
        self.assertEqual(data['search_handler'], self.req.href.bhsearch())

        data = process_request('/', enable_redirect=False, is_default=True)
        self.assertIn('search_handler', data)
        self.assertEqual(data['search_handler'], self.req.href.bhsearch())

        data = process_request('/', enable_redirect=True, is_default=True)
        self.assertIn('search_handler', data)
        self.assertEqual(data['search_handler'], self.req.href.bhsearch())

        for is_default in [False, True]:
            data = process_request('/search',
                                   enable_redirect=False,
                                   is_default=is_default)
            self.assertIn('search_handler', data)
            self.assertEqual(data['search_handler'], self.req.href.search())

        for is_default in [False, True]:
            data = process_request('/search',
                                   enable_redirect=True,
                                   is_default=is_default)
            self.assertIn('search_handler', data)
            self.assertEqual(data['search_handler'], self.req.href.bhsearch())

        for enable_redirect in [False, True]:
            for is_default in [False, True]:
                data = process_request('/bhsearch',
                                       enable_redirect=enable_redirect,
                                       is_default=is_default)
                self.assertIn('search_handler', data)
                self.assertEqual(data['search_handler'],
                                 self.req.href.bhsearch())

    def test_that_active_query_is_set(self):
        #arrange
        self.insert_ticket("Ticket 1", component="c1", status="new")
        self.insert_ticket("Ticket 2", component="c1", status="new")
        #act
        self.req.args[RequestParameters.TYPE] = "ticket"
        self.req.args[RequestParameters.QUERY] = "Ticket"
        self.req.args[RequestParameters.FILTER_QUERY] = [
            'component:"c1"',
            'status:"new"']
        data = self.process_request()
        #assert
        active_query = data["active_query"]
        self.assertEqual(active_query["label"], '"Ticket"')
        self.assertEqual(active_query["query"], "Ticket")
        self.assertNotIn("?q=", unquote(active_query["href"]))
        self.assertNotIn("&q=", unquote(active_query["href"]))
        self.assertIn("fq=", unquote(active_query["href"]))

    def test_redirects_if_product_env_is_used_to_access_search(self):
        self.env.config.set('bhsearch', 'global_quicksearch', "True")

        with self.product('xxx'):
            self.assertRaises(RequestDone, self.process_request)

        self.assertIn('/bhsearch', self.redirect_url)
        self.assertNotIn('/products', self.redirect_url)
        self.assertNotIn('product_prefix=xxx', self.redirect_url)
        self.assertTrue(self.redirect_permanent)

    def test_adds_product_filter_when_global_quicksearch_is_disabled(self):
        self.env.config.set('bhsearch', 'global_quicksearch', "false")

        with self.product('xxx'):
            self.assertRaises(RequestDone, self.process_request)

        self.assertIn('/bhsearch', self.redirect_url)
        self.assertNotIn('/products', self.redirect_url)
        self.assertIn('product_prefix=xxx', self.redirect_url)
        self.assertTrue(self.redirect_permanent)

    def _find_header(self, headers, name):
        for header in headers:
            if header["name"] == name:
                return header
        raise Exception("Header not found: %s" % name)

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


class RequestParametersTest(unittest.TestCase):
    def setUp(self):
        self.req = Mock(
            perm=MockPerm(),
            chrome={'logo': {}},
            href=Href("/main"),
            base_path=BASE_PATH,
            args=arg_list_to_args([]),
        )

    def test_can_parse_multiple_sort_terms(self):
        self.assertEqual(
            None,
            self._evaluate_sort("  "))
        self.assertEqual(
            None,
            self._evaluate_sort(" ,  , "))
        self.assertEqual(
            [SortInstruction("f1", ASC),],
            self._evaluate_sort(" f1 "))
        self.assertEqual(
            [SortInstruction("f1", ASC),],
            self._evaluate_sort(" f1 asc"))
        self.assertEqual(
            [SortInstruction("f1", DESC),],
            self._evaluate_sort("f1  desc"))
        self.assertEqual(
            [SortInstruction("f1", ASC), SortInstruction("f2", DESC)],
            self._evaluate_sort("f1, f2 desc"))

    def test_can_raise_error_on_invalid_sort_term(self):
        self.assertRaises(
            TracError,
            self._evaluate_sort,
            "f1  desc bb")

    def test_can_create_href_with_single_sort(self):
        href = RequestParameters(self.req).create_href(
            sort=SortInstruction("field1", ASC))
        href = unquote(href)
        self.assertIn("sort=field1+asc", href)

    def test_can_create_href_with_multiple_sort(self):
        href = RequestParameters(self.req).create_href(
            sort=[
                SortInstruction("field1", ASC),
                SortInstruction("field2", DESC),
            ])
        href = unquote(href)
        self.assertIn("sort=field1+asc,+field2+desc", href)

    def _evaluate_sort(self, sort_condition):
        self.req.args[RequestParameters.SORT] = sort_condition
        parameters = RequestParameters(self.req)
        return parameters.sort


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(WebUiTestCaseWithWhoosh, 'test'))
    test_suite.addTest(unittest.makeSuite(RequestParametersTest, 'test'))
    return test_suite

if __name__ == '__main__':
    unittest.main()
