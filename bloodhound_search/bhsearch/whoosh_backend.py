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

r"""Whoosh specific backend for Bloodhound Search plugin."""
from bhsearch.api import ISearchBackend, DESC, QueryResult, SCORE
import os
from trac.core import *
from trac.config import Option, PathOption
from trac.util.datefmt import utc
from whoosh.fields import *
from whoosh import index, sorting
from whoosh.qparser import QueryParser
from whoosh.searching import ResultsPage
from whoosh.sorting import FieldFacet
from whoosh.writing import AsyncWriter
from datetime import datetime, date

class WhooshBackend(Component):
    """
    Implements Whoosh SearchBackend interface
    """
    implements(ISearchBackend)

    index_dir_setting = Option('bhsearch', 'whoosh_index_dir', 'whoosh_index',
        """Relative path is resolved relatively to the
        directory of the environment.""")

    #This is schema prototype. It will be changed later
    #TODO: add other fields support, add dynamic field support
    SCHEMA = Schema(
        unique_id=ID(stored=True, unique=True),
        id=ID(stored=True),
        type=ID(stored=True),
        product=ID(stored=True),
        time=DATETIME(stored=True),
        author=ID(stored=True),
        component=KEYWORD(stored=True),
        status=KEYWORD(stored=True),
        resolution=KEYWORD(stored=True),
        keywords=KEYWORD(scorable=True),
        milestone=TEXT(spelling=True),
        summary=TEXT(stored=True),
        content=TEXT(stored=True),
        changes=TEXT(),
        )

    def __init__(self):
        self.index_dir = self.index_dir_setting
        if not os.path.isabs(self.index_dir):
            self.index_dir = os.path.join(self.env.path, self.index_dir)
        self.open_or_create_index_if_missing()

    #ISearchBackend methods
    def add_doc(self, doc, commit=True):
        """Add any type of  document index.

        The contents should be a dict with fields matching the search schema.
        The only required fields are type and id, everything else is optional.
        """
        # Really make sure it's unicode, because Whoosh won't have it any
        # other way.
        for key in doc:
            doc[key] = self._to_whoosh_format(doc[key])

        doc["unique_id"] = u"%s:%s" % (doc["type"], doc["id"])

        writer = AsyncWriter(self.index)
        committed = False
        try:
            #todo: remove it!!!
            self.log.debug("Doc to index: %s", doc)
            writer.update_document(**doc)
            writer.commit()
            committed = True
        finally:
            if not committed:
                writer.cancel()


    def query(self, query, sort = None, fields = None, boost = None, filters = None,
                  facets = None, pagenum = 1, pagelen = 20):

        with self.index.searcher() as searcher:
            parser = QueryParser("content", self.index.schema)
            if isinstance(query, basestring):
                query = unicode(query)
                parsed_query = parser.parse(unicode(query))
            else:
                parsed_query = query

            sortedby = self._prepare_sortedby(sort)
            groupedby = self._prepare_groupedby(facets)
            self.env.log.debug("Whoosh query to execute: %s, sortedby = %s, \
                               pagenum=%s, pagelen=%s, facets=%s",
                parsed_query,
                sortedby,
                pagenum,
                pagelen,
                groupedby,
            )
            raw_page = searcher.search_page(
                parsed_query,
                pagenum = pagenum,
                pagelen = pagelen,
                sortedby = sortedby,
                groupedby = groupedby,
            )
#            raw_page = ResultsPage(whoosh_results, pagenum, pagelen)
            results = self._process_results(raw_page, fields)
        return results

    def delete_doc(self, doc, commit=True):
        pass

    def commit(self):
        pass

    def optimize(self):
        pass

    def recreate_index(self):
        self.index = self._create_index()

    def open_or_create_index_if_missing(self):
        if index.exists_in(self.index_dir):
            self.index = index.open_dir(self.index_dir)
        else:
            self.index = self._create_index()


    def _to_whoosh_format(self, value):
        if isinstance(value, basestring):
            value = unicode(value)
        elif isinstance(value, datetime):
            value = self._convert_date_to_tz_naive_utc(value)
        return value

    def _convert_date_to_tz_naive_utc(self, value):
        """Convert datetime to naive utc datetime
        Whoosh can not read  from index datetime value with
        tzinfo=trac.util.datefmt.FixedOffset because of non-empty
        constructor"""
        if value.tzinfo:
            utc_time = value.astimezone(utc)
            value = utc_time.replace(tzinfo=None)
        return value

    def _from_whoosh_format(self, value):
        if isinstance(value, datetime):
            value = utc.localize(value)
        return value

    def _prepare_groupedby(self, facets):
        if not facets:
            return None
        groupedby = sorting.Facets()
        for facet_name in facets:
            groupedby.add_field(facet_name, allow_overlap=True, maptype=sorting.Count)
        return groupedby

    def _prepare_sortedby(self, sort):
        if not sort:
            return None
        sortedby = []
        for (field, order) in sort:
            if field.lower() == SCORE:
                if self._is_desc(order):
                    #We can implement later our own ScoreFacet with
                    # "score DESC" support
                    raise TracError("Whoosh does not support DESC score ordering.")
                sort_condition = sorting.ScoreFacet()
            else:
                sort_condition = sorting.FieldFacet(field, reverse=self._is_desc(order))
            sortedby.append(sort_condition)
        return sortedby

    def _is_desc(self, order):
        return (order.lower()==DESC)

    def _process_results(self, page, fields):
        # It's important to grab the hits first before slicing. Otherwise, this
        # can cause pagination failures.
        """
        :type fields: iterator
        :type page: ResultsPage
        """
        results = QueryResult()
        results.hits = page.total
        results.total_page_count = page.pagecount
        results.page_number = page.pagenum
        results.offset = page.offset
        results.facets = self._load_facets(page)

        docs = []
        for doc_offset, retrieved_record in enumerate(page):
            result_doc = self._process_record(fields, retrieved_record)
            docs.append(result_doc)
        results.docs = docs
        return results

    def _process_record(self, fields, retrieved_record):
        result_doc = dict()
        #add score field by default
        if not fields or SCORE in fields:
            score = retrieved_record.score
            result_doc[SCORE] = score

        if fields:
            for field in fields:
                if field in retrieved_record:
                    result_doc[field] = retrieved_record[field]
        else:
            for key, value in retrieved_record.items():
                result_doc[key] = value

        for key, value in result_doc.iteritems():
            result_doc[key] = self._from_whoosh_format(value)
        return result_doc

    def _load_facets(self, page):
        non_paged_results = page.results
        facet_names = non_paged_results.facet_names()
        if not facet_names:
            return None
        facets_result = dict()
        for name in facet_names:
            facets_result[name] = non_paged_results.groups(name)
        return facets_result

    def _create_index(self):
        self.log.info('Creating Whoosh index in %s' % self.index_dir)
        self._mkdir_if_not_exists()
        return index.create_in(self.index_dir, schema=self.SCHEMA)

    def _mkdir_if_not_exists(self):
        if not os.path.exists(self.index_dir):
            os.mkdir(self.index_dir)

        if not os.access(self.index_dir, os.W_OK):
            raise TracError(
                "The path to Whoosh index '%s' is not writable for the\
                 current user."
                % self.index_dir)

