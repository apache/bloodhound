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
from bhsearch.query_parser import DefaultQueryParser
from bhsearch.tests.utils import BaseBloodhoundSearchTest
from bhsearch.whoosh_backend import WhooshBackend
from trac.test import EnvironmentStub
from trac.util.datefmt import FixedOffset, utc
from whoosh import index, sorting, query
from whoosh.fields import Schema, ID, TEXT, KEYWORD
from whoosh.qparser import MultifieldPlugin, QueryParser, WhitespacePlugin, PhrasePlugin


class WhooshBackendTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        self.env = EnvironmentStub(enable=['bhsearch.*'])
        self.env.path = tempfile.mkdtemp('bhsearch-tempenv')
        self.whoosh_backend = WhooshBackend(self.env)
        self.whoosh_backend.recreate_index()
        self.default_parser = DefaultQueryParser(self.env)

    def tearDown(self):
        shutil.rmtree(self.env.path)
        self.env.reset_db()

    def test_can_retrieve_docs(self):
        self.whoosh_backend.add_doc(dict(id="1", type="ticket"))
        self.whoosh_backend.add_doc(dict(id="2", type="ticket"))
        result = self.whoosh_backend.query(
            query.Every(),
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
        result = self.whoosh_backend.query(query.Every())
        self.print_result(result)
        docs = result.docs
        self.assertEqual(
            {'id': '1', 'type': 'ticket', 'unique_id': 'ticket:1',
                "score": 1.0},
            docs[0])

    def test_can_select_fields(self):
        self.whoosh_backend.add_doc(dict(id="1", type="ticket"))
        result = self.whoosh_backend.query(query.Every(),
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
        result = whoosh_backend2.query(query.Every())
        self.assertEqual(2, result.hits)

    def test_can_multi_sort_asc(self):
        self.whoosh_backend.add_doc(dict(id="2", type="ticket2"))
        self.whoosh_backend.add_doc(dict(id="3", type="ticket1"))
        self.whoosh_backend.add_doc(dict(id="4", type="ticket3"))
        self.whoosh_backend.add_doc(dict(id="1", type="ticket1"))
        result = self.whoosh_backend.query(
            query.Every(),
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
            query.Every(),
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

        parsed_query = self.default_parser.parse("summary:texttofind")

        result = self.whoosh_backend.query(
            parsed_query,
            sort = [(SCORE, ASC), ("time", DESC)],
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
            query.Every(),
            sort = [("type", ASC), ("id", DESC)],
            fields=("id", "type"),
            facets= ("type", "product")
        )
        self.print_result(result)
        self.assertEqual(3, result.hits)
        facets = result.facets
        self.assertEqual({"ticket":2, "wiki":1}, facets["type"])
        self.assertEqual({"A":2, "B":1}, facets["product"])

    def test_can_do_facet_if_filed_missing_TODO(self):
        self.whoosh_backend.add_doc(dict(id="1", type="ticket"))
        self.whoosh_backend.add_doc(dict(id="2", type="ticket", status="New"))
        result = self.whoosh_backend.query(
            query.Every(),
            facets= ("type", "status")
        )
        self.print_result(result)
        self.assertEqual(2, result.hits)
        facets = result.facets
        self.assertEqual({"ticket":2}, facets["type"])
        self.assertEqual({None: 1, 'New': 1}, facets["status"])

    def test_can_return_empty_result(self):
        result = self.whoosh_backend.query(
            query.Every(),
            sort = [("type", ASC), ("id", DESC)],
            fields=("id", "type"),
            facets= ("type", "product")
        )
        self.print_result(result)
        self.assertEqual(0, result.hits)

    def test_can_search_time_with_utc_tzinfo(self):
        time = datetime(2012, 12, 13, 11, 8, 34, 711957, tzinfo=FixedOffset(0, 'UTC'))
        self.whoosh_backend.add_doc(dict(id="1", type="ticket", time=time))
        result = self.whoosh_backend.query(query.Every())
        self.print_result(result)
        self.assertEqual(time, result.docs[0]["time"])

    def test_can_search_time_without_tzinfo(self):
        time = datetime(2012, 12, 13, 11, 8, 34, 711957, tzinfo=None)
        self.whoosh_backend.add_doc(dict(id="1", type="ticket", time=time))
        result = self.whoosh_backend.query(query.Every())
        self.print_result(result)
        self.assertEqual(time.replace(tzinfo=utc), result.docs[0]["time"])

    def test_can_search_time_with_non_utc_tzinfo(self):
        hours = 8
        tz_diff = 1
        time = datetime(2012, 12, 13, 11, hours, 34, 711957,
            tzinfo=FixedOffset(tz_diff, "just_one_timezone"))
        self.whoosh_backend.add_doc(dict(id="1", type="ticket", time=time))
        result = self.whoosh_backend.query(query.Every())
        self.print_result(result)
        self.assertEqual(datetime(2012, 12, 13, 11, hours-tz_diff, 34, 711957,
                    tzinfo=utc), result.docs[0]["time"])


    def test_can_apply_filter_and_facet(self):
        self.whoosh_backend.add_doc(dict(id="1", type="ticket"))
        self.whoosh_backend.add_doc(dict(id="2", type="wiki" ))
        result = self.whoosh_backend.query(
            query.Every(),
            filter=[("type", "ticket")],
            facets=["type"]
        )
        self.print_result(result)
        self.assertEqual(1, result.hits)
        self.assertEqual("ticket", result.docs[0]["type"])


    @unittest.skip("TODO clarify behavior on Whoosh mail list")
    def test_can_search_id_and_summary_TODO(self):
        #arrange
        self.insert_ticket("test x")
        self.insert_ticket("test 1")

        fieldboosts = dict(
            id = 1,
            summary = 1,
        )

        mfp = MultifieldPlugin(list(fieldboosts.keys()),)
        pins = [WhitespacePlugin,
                PhrasePlugin,
                mfp]
        parser =  QueryParser(None, WhooshBackend.SCHEMA, plugins=pins)

        parsed_query = parser.parse("1")
        result = self.whoosh_backend.query(parsed_query)
        self.print_result(result)
        self.assertEqual(2, result.hits)

class WhooshFunctionalityTestCase(unittest.TestCase):
    def setUp(self):
        self.index_dir = tempfile.mkdtemp('whoosh_index')

    def tearDown(self):
        shutil.rmtree(self.index_dir)

    def test_groupedby_empty_field(self):
        schema = Schema(
                unique_id=ID(stored=True, unique=True),
                id=ID(stored=True),
                type=ID(stored=True),
                status=KEYWORD(stored=True),
                content=TEXT(stored=True),
                )

        ix = index.create_in(self.index_dir, schema=schema)
        with ix.writer() as w:
            w.add_document(unique_id="1",type="type1")
            w.add_document(unique_id="2",type="type2", status="New")

        facet_fields = ("type", "status" )
        groupedby = facet_fields
        with ix.searcher() as s:
            r = s.search(
                query.Every(),
                groupedby=groupedby,
                maptype=sorting.Count,
            )
            facets = self._load_facets(r)
            print len(r) == 2
        print facets
        self.assertEquals(
            {'status': {None: 1, 'New': 1}, 'type': {'type1': 1, 'type2': 1}},
            facets)

    def test_groupedby_empty_field(self):
        """
        Whoosh 2.4 raises an error when simultaneously using filters and facets
        in search:
            AttributeError: 'FacetCollector' object has no attribute 'offset'

        The problem should be fixed in the next release. For more info read
        https://bitbucket.org/mchaput/whoosh/issue/274

        For the time of being, whoosh-backend have to introduce workaround in
        order to fix the problem. This unit-test is just a reminder to remove
        workaround when the fixed version of Whoosh is applied.
        """
        schema = Schema(
                unique_id=ID(stored=True, unique=True),
                type=ID(stored=True),
                )

        ix = index.create_in(self.index_dir, schema=schema)
        with ix.writer() as w:
            w.add_document(unique_id=u"1",type=u"type1")
            w.add_document(unique_id=u"2",type=u"type2")

        with ix.searcher() as s:
            with self.assertRaises(AttributeError):
                s.search(
                    query.Every(),
                    groupedby=("type"),
                    maptype=sorting.Count,
                    filter=query.Term("type", "type1")
                )

#    def _prepare_groupedby(self, facets):
#        if not facets:
#            return None
#        groupedby = sorting.Facets()
#        for facet_name in facets:
#            groupedby.add_field(facet_name, allow_overlap=True, maptype=sorting.Count)
#        return groupedby

    def _load_facets(self, non_paged_results):
        facet_names = non_paged_results.facet_names()
        if not facet_names:
            return None
        facets_result = dict()
        for name in facet_names:
            facets_result[name] = non_paged_results.groups(name)
        return facets_result



def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(WhooshBackendTestCase, 'test'))
    suite.addTest(unittest.makeSuite(WhooshFunctionalityTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main()