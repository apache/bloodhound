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
from datetime import datetime
import os
import shutil
import tempfile

from trac.util.datefmt import FixedOffset, utc

from bhsearch.api import ASC, DESC, SCORE, SortInstruction
from bhsearch.query_parser import DefaultQueryParser
from bhsearch.tests import unittest
from bhsearch.tests.base import BaseBloodhoundSearchTest
from bhsearch.whoosh_backend import WhooshBackend, \
    WhooshEmptyFacetErrorWorkaround
from whoosh import index, query, sorting
from whoosh.fields import ID, KEYWORD, TEXT, Schema
from whoosh.qparser import MultifieldParser, MultifieldPlugin, PhrasePlugin, \
    QueryParser, WhitespacePlugin


class WhooshBackendTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        super(WhooshBackendTestCase, self).setUp()
        self.whoosh_backend = WhooshBackend(self.env)
        self.whoosh_backend.recreate_index()
        self.parser = DefaultQueryParser(self.env)

    def test_can_retrieve_docs(self):
        self.whoosh_backend.add_doc(dict(id="1", type="ticket"))
        self.whoosh_backend.add_doc(dict(id="2", type="ticket"))
        result = self.whoosh_backend.query(
            query.Every(),
            sort = [SortInstruction("id", ASC)],
        )
        self.print_result(result)
        self.assertEqual(2, result.hits)
        docs = result.docs
        self.assertEqual(
            {'id': u'1', 'type': u'ticket', 'unique_id': u'empty:ticket:1',
             'score': u'1'},
            docs[0])
        self.assertEqual(
            {'id': u'2', 'type': u'ticket', 'unique_id': u'empty:ticket:2',
             'score': u'2'},
            docs[1])

    def test_can_return_all_fields(self):
        self.whoosh_backend.add_doc(dict(id="1", type="ticket"))
        result = self.whoosh_backend.query(query.Every())
        self.print_result(result)
        docs = result.docs
        self.assertEqual(
            {'id': u'1', 'type': u'ticket', 'unique_id': u'empty:ticket:1',
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

    def test_can_apply_multiple_sort_conditions_asc(self):
        self.whoosh_backend.add_doc(dict(id="2", type="ticket2"))
        self.whoosh_backend.add_doc(dict(id="3", type="ticket1"))
        self.whoosh_backend.add_doc(dict(id="4", type="ticket3"))
        self.whoosh_backend.add_doc(dict(id="1", type="ticket1"))
        result = self.whoosh_backend.query(
            query.Every(),
            sort = [SortInstruction("type", ASC), SortInstruction("id", ASC)],
            fields=("id", "type"),
        )
        self.print_result(result)
        self.assertEqual([{'type': 'ticket1', 'id': '1'},
                          {'type': 'ticket1', 'id': '3'},
                          {'type': 'ticket2', 'id': '2'},
                          {'type': 'ticket3', 'id': '4'}],
            result.docs)

    def test_can_apply_multiple_sort_conditions_desc(self):
        self.whoosh_backend.add_doc(dict(id="2", type="ticket2"))
        self.whoosh_backend.add_doc(dict(id="3", type="ticket1"))
        self.whoosh_backend.add_doc(dict(id="4", type="ticket3"))
        self.whoosh_backend.add_doc(dict(id="1", type="ticket1"))
        result = self.whoosh_backend.query(
            query.Every(),
            sort = [SortInstruction("type", ASC), SortInstruction("id", DESC)],
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

        parsed_query = self.parser.parse("summary:texttofind")

        result = self.whoosh_backend.query(
            parsed_query,
            sort = [
                SortInstruction(SCORE, ASC),
                SortInstruction("time", DESC)
            ],
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
            sort = [SortInstruction("type", ASC), SortInstruction("id", DESC)],
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
            sort = [SortInstruction("type", ASC), SortInstruction("id", DESC)],
            fields=("id", "type"),
            facets= ("type", "product")
        )
        self.print_result(result)
        self.assertEqual(0, result.hits)

    def test_can_search_time_with_utc_tzinfo(self):
        time = datetime(2012, 12, 13, 11, 8, 34, 711957,
            tzinfo=FixedOffset(0, 'UTC'))
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
            filter=query.Term("type", "ticket"),
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

    def test_no_index_error_when_counting_facet_on_missing_field(self):
        """
        Whoosh 2.4.1 raises "IndexError: list index out of range"
        when search contains facets on field that is missing in at least one
        document in the index. The error manifests only when index contains
        more than one segment

        Introduced workaround should solve this problem.
        """
        #add more tickets to make sure we have more than one segment in index
        count = 20
        for i in range(count):
            self.insert_ticket("test %s" % (i))

        result = self.whoosh_backend.query(
            query.Every(),
            facets=["milestone"]
        )
        self.assertEquals(count, result.hits)

    def test_can_query_missing_field_and_type(self):
        self.whoosh_backend.add_doc(dict(id="1", type="ticket"))
        self.whoosh_backend.add_doc(dict(id="2", type="ticket", milestone="A"))
        self.whoosh_backend.add_doc(dict(id="3", type="wiki"))
        filter = self.parser.parse_filters(["NOT (milestone:*)", "type:ticket"])
        result = self.whoosh_backend.query(
            query.Every(),
            filter=filter,
        )
        self.print_result(result)
        self.assertEqual(1, result.hits)
        self.assertEqual("1", result.docs[0]["id"])


    def test_can_query_missing_field(self):
        self.whoosh_backend.add_doc(dict(id="1", type="ticket"))
        self.whoosh_backend.add_doc(dict(id="2", type="ticket", milestone="A"))
        filter = self.parser.parse_filters(["NOT (milestone:*)"])
        result = self.whoosh_backend.query(
            query.Every(),
            filter=filter,
        )
        self.print_result(result)
        self.assertEqual(1, result.hits)
        self.assertEqual("1", result.docs[0]["id"])


    @unittest.skip("TODO clarify behavior on Whoosh mail list")
    def test_can_query_missing_field_and_type_with_no_results(self):
        self.whoosh_backend.add_doc(dict(id="1", type="ticket"))
        self.whoosh_backend.add_doc(dict(id="3", type="wiki"))
        filter = self.parser.parse_filters(["NOT (milestone:*)", "type:ticket"])
        result = self.whoosh_backend.query(
            query.Every(),
            filter=filter,
        )
        self.print_result(result)
        self.assertEqual(0, result.hits)

    def test_can_highlight_given_terms(self):
        term = 'search_term'
        text = "foo foo %s bar bar" % term
        self.whoosh_backend.add_doc(dict(id="1", type="ticket", content=text))
        self.whoosh_backend.add_doc(dict(id="3", type="wiki", content=text))
        search_query = self.parser.parse(term)

        result = self.whoosh_backend.query(
            search_query,
            highlight=True,
            highlight_fields=['content', 'summary']
        )
        self.print_result(result)

        self.assertEqual(len(result.highlighting), 2)
        for highlight in result.highlighting:
            self.assertIn(self._highlighted(term), highlight['content'])
            self.assertEquals("", highlight['summary'])

    def test_that_highlighting_escapes_html(self):
        term = 'search_term'
        text = "bla <a href=''>%s bar</a> bla" % term
        self.whoosh_backend.add_doc(dict(id="1", type="ticket", content=text))
        search_query = self.parser.parse(term)

        result = self.whoosh_backend.query(
            search_query,
            highlight=True,
            highlight_fields=['content']
        )
        self.print_result(result)

        self.assertEqual(len(result.highlighting), 1)
        highlight = result.highlighting[0]
        self.assertEquals(
            "bla &lt;a href=''&gt;<em>search_term</em> bar&lt;/a&gt; bla",
            highlight['content'])

    def test_highlights_all_text_fields_by_default(self):
        term = 'search_term'
        text = "foo foo %s bar bar" % term
        self.whoosh_backend.add_doc(dict(id="1", type="ticket", content=text))
        self.whoosh_backend.add_doc(dict(id="3", type="wiki", content=text))
        search_query = self.parser.parse(term)

        result = self.whoosh_backend.query(
            search_query,
            highlight=True,
        )
        self.print_result(result)

        self.assertEqual(len(result.highlighting), 2)
        for highlight in result.highlighting:
            self.assertIn('content', highlight)
            self.assertIn('summary', highlight)
            self.assertIn(self._highlighted(term), highlight['content'])

    def test_only_highlights_terms_in_fields_that_match_query(self):
        term = 'search_term'
        self.whoosh_backend.add_doc(dict(id=term, type="wiki", content=term))
        self.whoosh_backend.add_doc(dict(id=term, type="ticket", summary=term))
        search_query = self.parser.parse('id:%s' % term)

        result = self.whoosh_backend.query(
            search_query,
            highlight=True,
            highlight_fields=["id", "content", "summary"]
        )
        self.print_result(result)

        self.assertEqual(len(result.highlighting), 2)
        for highlight in result.highlighting:
            self.assertIn(self._highlighted(term), highlight['id'])
            self.assertNotIn(self._highlighted(term), highlight['summary'])
            self.assertNotIn(self._highlighted(term), highlight['content'])

    def _highlighted(self, term):
        return '<em>%s</em>' % term


class WhooshIndexCreationTests(BaseBloodhoundSearchTest):
    def setUp(self):
        super(WhooshIndexCreationTests, self).setUp()
        self.index_dir = os.path.join(self.env.path, 'whoosh_index')
        if not os.path.exists(self.index_dir):
            os.mkdir(self.index_dir)

    def test_does_not_automatically_create_index(self):
        whoosh_backend = WhooshBackend(self.env)

        self.assertIs(whoosh_backend.index, None)
        self.assertEqual(whoosh_backend.is_index_outdated(), True)

        whoosh_backend.recreate_index()
        self.assertEqual(whoosh_backend.is_index_outdated(), False)
        self.assertIsNot(whoosh_backend.index, None)

    def test_detects_that_index_needs_upgrade(self):
        wrong_schema = Schema(content=TEXT())
        index.create_in(self.index_dir, schema=wrong_schema)

        whoosh_backend = WhooshBackend(self.env)
        self.assertEqual(whoosh_backend.is_index_outdated(), True)

        whoosh_backend.recreate_index()
        self.assertEqual(whoosh_backend.is_index_outdated(), False)


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
            w.add_document(unique_id=u"1", type=u"type1")
            w.add_document(unique_id=u"2", type=u"type2", status=u"New")

        facet_fields = (u"type", u"status" )
        groupedby = facet_fields
        with ix.searcher() as s:
            r = s.search(
                query.Every(),
                groupedby=groupedby,
                maptype=sorting.Count,
            )
            facets = self._load_facets(r)
        self.assertEquals(
            {'status': {None: 1, 'New': 1}, 'type': {'type1': 1, 'type2': 1}},
            facets)

    def test_out_of_range_on_empty_facets(self):
        """
        Whoosh raises exception IndexError: list index out of range
        when search contains facets on field that is missing in at least one
        document in the index. The error manifests only when index contains
        more than one segment

        The problem expected to be fixed in the next release.

        For the time of being, whoosh-backend have to introduce workaround in
        order to fix the problem. This unit-test is just a reminder to remove
        workaround when the fixed version of Whoosh is applied.
        """
        schema = Schema(
                unique_id=ID(stored=True, unique=True),
                status=ID(stored=True),
                )

#        ix = RamStorage().create_index(schema)
        ix = index.create_in(self.index_dir, schema=schema)
        def insert_docs():
            with ix.writer() as w:
                for i in range(10):
                    w.add_document(unique_id=unicode(i))

        #the problem occurs only when index contains more than one segment
        insert_docs()
        insert_docs()

        with ix.searcher() as s:
            with self.assertRaises(IndexError):
                s.search(
                    query.Every(),
                    groupedby=(u"status"),
                    maptype=sorting.Count,
                )

    def _load_facets(self, non_paged_results):
        facet_names = non_paged_results.facet_names()
        if not facet_names:
            return None
        facets_result = dict()
        for name in facet_names:
            facets_result[name] = non_paged_results.groups(name)
        return facets_result

    def test_can_auto_commit(self):
        # pylint: disable=unused-argument

        schema = Schema(
                unique_id=ID(stored=True, unique=True),
                type=ID(stored=True),
                )

        ix = index.create_in(self.index_dir, schema=schema)
        with ix.writer() as w:
            w.add_document(unique_id=u"1", type=u"type1")
            w.add_document(unique_id=u"2", type=u"type2")

        with ix.searcher() as s:
            results = s.search(query.Every())
            self.assertEquals(2, len(results))

    def test_can_auto_cancel(self):
        schema = Schema(
                unique_id=ID(stored=True, unique=True),
                type=ID(stored=True),
                )

        ix = index.create_in(self.index_dir, schema=schema)
        try:
            with ix.writer() as w:
                w.add_document(unique_id=u"1", type=u"type1")
                w.add_document(unique_id=u"2", type=u"type2")
                raise Exception("some exception")
        except Exception:
            pass

        with ix.searcher() as s:
            results = s.search(query.Every())
            self.assertEquals(0, len(results))

    def test_handles_stop_words_in_queries(self):
        schema = WhooshBackend.SCHEMA
        ix = index.create_in(self.index_dir, schema=schema)
        with ix.writer() as w:
            w.add_document(content=u"A nice sentence with stop words.")

        with ix.searcher() as s:
            query_text = u"with stop"

            # field_names both ignore stop words
            q = MultifieldParser(['content', 'summary'],
                                 WhooshBackend.SCHEMA).parse(query_text)
            self.assertEqual(unicode(q.simplify(s)),
                             u'((content:with OR summary:with) AND '
                             u'(content:stop OR summary:stop))')
            self.assertEqual(len(s.search(q)), 1)

            # 'content' and 'id' ignores stop words
            q = MultifieldParser(['content', 'id'],
                                 WhooshBackend.SCHEMA).parse(query_text)
            self.assertEqual(unicode(q.simplify(s)),
                             u'((content:with OR id:with) AND '
                             u'(content:stop OR id:stop))')
            self.assertEqual(len(s.search(q)), 1)

    def test_can_filter_to_no_results(self):
        schema = Schema(
            id=ID(stored=True),
            filter=TEXT(stored=True),
        )

        ix = index.create_in(self.index_dir, schema=schema)
        with ix.writer() as w:
            w.add_document(id=u"1", filter=u"f1")
            w.add_document(id=u"2", filter=u"f2")

        with ix.searcher() as s:
            r = s.search(
                query.Every(),
                filter=QueryParser('', schema).parse(u"filter:other")
            )
        self.assertEquals(len(r), 0)


class WhooshEmptyFacetErrorWorkaroundTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        super(WhooshEmptyFacetErrorWorkaroundTestCase, self).setUp()
        self.whoosh_backend = WhooshBackend(self.env)
        self.whoosh_backend.recreate_index()
        self.parser = DefaultQueryParser(self.env)
        self.empty_facet_workaround = WhooshEmptyFacetErrorWorkaround(self.env)

    def tearDown(self):
        shutil.rmtree(self.env.path)
        self.env.reset_db()

    def test_set_should_not_be_empty_fields(self):
        self.insert_ticket("test x")
        result = self.whoosh_backend.query(query.Every())
        self.print_result(result)
        doc = result.docs[0]
        null_marker = WhooshEmptyFacetErrorWorkaround.NULL_MARKER
        self.assertEqual(null_marker, doc["component"])
        self.assertEqual(null_marker, doc["status"])
        self.assertEqual(null_marker, doc["milestone"])

    def test_can_fix_query_filter(self):
        parsed_filter = self.parser.parse_filters(
            ["type:ticket", "NOT (milestone:*)"])
        query_parameters = dict(filter=parsed_filter)
        self.empty_facet_workaround.query_pre_process(
            query_parameters)

        result_filter = query_parameters["filter"]
        self.assertEquals('(type:ticket AND milestone:empty)',
            str(result_filter))

    def test_does_interfere_query_filter_if_not_needed(self):
        parsed_filter = self.parser.parse_filters(
            ["type:ticket", "milestone:aaa"])
        query_parameters = dict(filter=parsed_filter)
        self.empty_facet_workaround.query_pre_process(
            query_parameters)

        result_filter = query_parameters["filter"]
        self.assertEquals('(type:ticket AND milestone:aaa)',
            str(result_filter))

def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(WhooshBackendTestCase, 'test'))
    test_suite.addTest(unittest.makeSuite(WhooshFunctionalityTestCase, 'test'))
    test_suite.addTest(
        unittest.makeSuite(WhooshEmptyFacetErrorWorkaroundTestCase, 'test'))
    return test_suite

if __name__ == '__main__':
    unittest.main()
