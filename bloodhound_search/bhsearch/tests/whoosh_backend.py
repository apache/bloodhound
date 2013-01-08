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

import unittest
import tempfile
import shutil
from bhsearch.api import ASC, DESC, SCORE
from bhsearch.tests.utils import BaseBloodhoundSearchTest
from bhsearch.whoosh_backend import WhooshBackend
from trac.test import EnvironmentStub
from trac.util.datefmt import FixedOffset, utc
from whoosh.qparser import MultifieldParser, MultifieldPlugin, syntax, QueryParser, WhitespacePlugin, PhrasePlugin, PlusMinusPlugin


class WhooshBackendTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        self.env = EnvironmentStub(enable=['bhsearch.*'])
        self.env.path = tempfile.mkdtemp('bhsearch-tempenv')
#        self.perm = PermissionSystem(self.env)
        self.whoosh_backend = WhooshBackend(self.env)
        self.whoosh_backend.recreate_index()

    def tearDown(self):
        shutil.rmtree(self.env.path)
        self.env.reset_db()

    def test_can_retrieve_docs(self):
        self.whoosh_backend.add_doc(dict(id="1", type="ticket"))
        self.whoosh_backend.add_doc(dict(id="2", type="ticket"))
        result = self.whoosh_backend.query(
#        result = self.search_api.query(
            "*:*",
            sort = [("id", ASC)],
        )
        self.print_result(result)
        self.assertEqual(2, result.hits)
        docs = result.docs
        self.assertEqual(
            {'id': '1', 'type': 'ticket', 'unique_id': 'ticket:1',
             'score': u'1'},
            docs[0])
        self.assertEqual(
            {'id': '2', 'type': 'ticket', 'unique_id': 'ticket:2',
             'score': u'2'},
            docs[1])

    def test_can_return_all_fields(self):
        self.whoosh_backend.add_doc(dict(id="1", type="ticket"))
        result = self.whoosh_backend.query("*:*")
        self.print_result(result)
        docs = result.docs
        self.assertEqual(
            {'id': '1', 'type': 'ticket', 'unique_id': 'ticket:1',
                "score": 1.0},
            docs[0])

    def test_can_select_fields(self):
        self.whoosh_backend.add_doc(dict(id="1", type="ticket"))
        result = self.whoosh_backend.query("*:*",
            fields=("id", "type"))
        self.print_result(result)
        docs = result.docs
        self.assertEqual(
            {'id': '1', 'type': 'ticket'},
            docs[0])


    def test_can_survive_after_restart(self):
        self.whoosh_backend.add_doc(dict(id="1", type="ticket"))
        whoosh_backend2 = WhooshBackend(self.env)
        whoosh_backend2.add_doc(dict(id="2", type="ticket"))
        result = whoosh_backend2.query("*:*")
        self.assertEqual(2, result.hits)

    def test_can_multi_sort_asc(self):
        self.whoosh_backend.add_doc(dict(id="2", type="ticket2"))
        self.whoosh_backend.add_doc(dict(id="3", type="ticket1"))
        self.whoosh_backend.add_doc(dict(id="4", type="ticket3"))
        self.whoosh_backend.add_doc(dict(id="1", type="ticket1"))
        result = self.whoosh_backend.query(
            "*:*",
            sort = [("type", ASC), ("id", ASC)],
            fields=("id", "type"),
        )
        self.print_result(result)
        self.assertEqual([{'type': 'ticket1', 'id': '1'},
                          {'type': 'ticket1', 'id': '3'},
                          {'type': 'ticket2', 'id': '2'},
                          {'type': 'ticket3', 'id': '4'}],
            result.docs)

    def test_can_multi_sort_desc(self):
        self.whoosh_backend.add_doc(dict(id="2", type="ticket2"))
        self.whoosh_backend.add_doc(dict(id="3", type="ticket1"))
        self.whoosh_backend.add_doc(dict(id="4", type="ticket3"))
        self.whoosh_backend.add_doc(dict(id="1", type="ticket1"))
        result = self.whoosh_backend.query(
            "*:*",
            sort = [("type", ASC), ("id", DESC)],
            fields=("id", "type"),
        )
        self.print_result(result)
        self.assertEqual([{'type': 'ticket1', 'id': '3'},
                          {'type': 'ticket1', 'id': '1'},
                          {'type': 'ticket2', 'id': '2'},
                          {'type': 'ticket3', 'id': '4'}],
            result.docs)

    def test_can_sort_by_score_and_date(self):
        the_first_date = datetime(2012, 12, 1)
        the_second_date = datetime(2012, 12, 2)
        the_third_date = datetime(2012, 12, 3)

        exact_match_string = "texttofind"
        not_exact_match_string = "texttofind bla"

        self.whoosh_backend.add_doc(dict(
            id="1",
            type="ticket",
            summary=not_exact_match_string,
            time=the_first_date,
        ))
        self.whoosh_backend.add_doc(dict(
            id="2",
            type="ticket",
            summary=exact_match_string,
            time=the_second_date,
        ))
        self.whoosh_backend.add_doc(dict(
            id="3",
            type="ticket",
            summary=not_exact_match_string,
            time=the_third_date,
        ))
        self.whoosh_backend.add_doc(dict(
            id="4",
            type="ticket",
            summary="some text out of search scope",
            time=the_third_date,
        ))
        result = self.whoosh_backend.query(
            "summary:texttofind",
            sort = [(SCORE, ASC), ("time", DESC)],
#            fields=("id", "type"),
        )
        self.print_result(result)
        self.assertEqual(3, result.hits)
        docs = result.docs
        #must be found first, because the highest score (of exact match)
        self.assertEqual("2", docs[0]["id"])
        #must be found second, because the time order DESC
        self.assertEqual("3", docs[1]["id"])
        #must be found third, because the time order DESC
        self.assertEqual("1", docs[2]["id"])

    def test_can_do_facet_count(self):
        self.whoosh_backend.add_doc(dict(id="1", type="ticket", product="A"))
        self.whoosh_backend.add_doc(dict(id="2", type="ticket", product="B"))
        self.whoosh_backend.add_doc(dict(id="3", type="wiki", product="A"))
        result = self.whoosh_backend.query(
            "*:*",
            sort = [("type", ASC), ("id", DESC)],
            fields=("id", "type"),
            facets= ("type", "product")
        )
        self.print_result(result)
        self.assertEqual(3, result.hits)
        facets = result.facets
        self.assertEqual({"ticket":2, "wiki":1}, facets["type"])
        self.assertEqual({"A":2, "B":1}, facets["product"])

    @unittest.skip(
        "Fix this, check why exception is raise on Whoosh mailing list")
    #TODO: fix this!!!!
    def test_can_do_facet_if_filed_missing_TODO(self):
        self.whoosh_backend.add_doc(dict(id="1", type="ticket"))
        self.whoosh_backend.add_doc(dict(id="2", type="ticket", status="New"))
        result = self.whoosh_backend.query(
            "*:*",
            facets= ("type", "status")
        )
        self.print_result(result)
        self.assertEqual(2, result.hits)
        facets = result.facets
        self.assertEqual({"ticket":2}, facets["type"])
        self.assertEqual({"new":1}, facets["status"])

    def test_can_return_empty_result(self):
        result = self.whoosh_backend.query(
            "*:*",
            sort = [("type", ASC), ("id", DESC)],
            fields=("id", "type"),
            facets= ("type", "product")
        )
        self.print_result(result)
        self.assertEqual(0, result.hits)

    def test_can_search_time_with_utc_tzinfo(self):
        time = datetime(2012, 12, 13, 11, 8, 34, 711957, tzinfo=FixedOffset(0, 'UTC'))
        self.whoosh_backend.add_doc(dict(id="1", type="ticket", time=time))
        result = self.whoosh_backend.query("*:*")
        self.print_result(result)
        self.assertEqual(time, result.docs[0]["time"])

    def test_can_search_time_without_tzinfo(self):
        time = datetime(2012, 12, 13, 11, 8, 34, 711957, tzinfo=None)
        self.whoosh_backend.add_doc(dict(id="1", type="ticket", time=time))
        result = self.whoosh_backend.query("*:*")
        self.print_result(result)
        self.assertEqual(time.replace(tzinfo=utc), result.docs[0]["time"])

    def test_can_search_time_with_non_utc_tzinfo(self):
        hours = 8
        tz_diff = 1
        time = datetime(2012, 12, 13, 11, hours, 34, 711957,
            tzinfo=FixedOffset(tz_diff, "just_one_timezone"))
        self.whoosh_backend.add_doc(dict(id="1", type="ticket", time=time))
        result = self.whoosh_backend.query("*:*")
        self.print_result(result)
        self.assertEqual(datetime(2012, 12, 13, 11, hours-tz_diff, 34, 711957,
                    tzinfo=utc), result.docs[0]["time"])

    @unittest.skip("TODO clarify behavior on Whoosh mail list")
    def test_can_search_id_and_summary(self):
        #arrange
        self.insert_ticket("test x")
        self.insert_ticket("test 1")

#        field_boosts = dict(
#            id = 6,
#            type = 2,
#            summary = 5,
#            author = 3,
#            milestone = 2,
#            keywords = 2,
#            component = 2,
#            status = 2,
#            content = 1,
#            changes = 0.8,
#        )
        fieldboosts = dict(
            id = 1,
            summary = 1,
        )

#        parser = MultifieldParser(
#            fieldboosts.keys(),
#            WhooshBackend.SCHEMA,
##            fieldboosts=field_boosts
#        )

        mfp = MultifieldPlugin(list(fieldboosts.keys()),
#                                       fieldboosts=fieldboosts,
#                                       group=syntax.DisMaxGroup
        )
        pins = [WhitespacePlugin,
#                PlusMinusPlugin,
                PhrasePlugin,
                mfp]
        parser =  QueryParser(None, WhooshBackend.SCHEMA, plugins=pins)


        parsed_query = parser.parse(u"1")
#        parsed_query = parser.parse(u"test")
        result = self.whoosh_backend.query(parsed_query)
        self.print_result(result)
        self.assertEqual(2, result.hits)


def suite():
    return unittest.makeSuite(WhooshBackendTestCase, 'test')

if __name__ == '__main__':
    unittest.main()
