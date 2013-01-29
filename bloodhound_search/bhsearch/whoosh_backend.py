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
from bhsearch.api import ISearchBackend, DESC, QueryResult, SCORE, \
    IDocIndexPreprocessor, IResultPostprocessor, IndexFields, \
    IQueryPreprocessor
import os
from trac.core import Component, implements, TracError
from trac.config import Option
from trac.util.text import empty
from trac.util.datefmt import utc
from whoosh.fields import Schema, ID, DATETIME, KEYWORD, TEXT
#from whoosh import index, sorting, query
import whoosh
from whoosh.writing import AsyncWriter
from datetime import datetime

UNIQUE_ID = "unique_id"

class WhooshBackend(Component):
    """
    Implements Whoosh SearchBackend interface
    """
    implements(ISearchBackend)

    index_dir_setting = Option('bhsearch', 'whoosh_index_dir', 'whoosh_index',
        """Relative path is resolved relatively to the
        directory of the environment.""")

    #This is schema prototype. It will be changed later
    #TODO: add other fields support, add dynamic field support.
    #Schema must be driven by index participants
    SCHEMA = Schema(
        unique_id=ID(stored=True, unique=True),
        id=ID(stored=True),
        type=ID(stored=True),
        product=ID(stored=True),
        milestone=ID(stored=True),
        time=DATETIME(stored=True),
        due=DATETIME(stored=True),
        completed=DATETIME(stored=True),
        author=ID(stored=True),
        component=ID(stored=True),
        status=ID(stored=True),
        resolution=ID(stored=True),
        keywords=KEYWORD(scorable=True),
        summary=TEXT(stored=True),
        content=TEXT(stored=True),
        changes=TEXT(),
        )

    def __init__(self):
        self.index_dir = self.index_dir_setting
        if not os.path.isabs(self.index_dir):
            self.index_dir = os.path.join(self.env.path, self.index_dir)
        self.index = self._open_or_create_index_if_missing()

    #ISearchBackend methods
    def start_operation(self):
        return dict(writer = self._create_writer())

    def _create_writer(self):
        return AsyncWriter(self.index)

    def add_doc(self, doc, writer=None):
        """Add any type of  document index.

        The contents should be a dict with fields matching the search schema.
        The only required fields are type and id, everything else is optional.
        """
        is_local_writer = False
        if writer is None:
            is_local_writer = True
            writer = self._create_writer()

        self._reformat_doc(doc)
        doc[UNIQUE_ID] = self._create_unique_id(doc["type"], doc["id"])
        self.log.debug("Doc to index: %s", doc)
        try:
            writer.update_document(**doc)
            if is_local_writer:
                writer.commit()
        except:
            if is_local_writer:
                writer.cancel()
            raise

    def _reformat_doc(self, doc):
        """
        Strings must be converted unicode format accepted by Whoosh.
        """
        for key, value in doc.items():
            if key is None:
                del doc[None]
            elif value is None:
                del doc[key]
            elif isinstance(value, basestring) and value == "":
                del doc[key]
            else:
                doc[key] = self._to_whoosh_format(value)

    def delete_doc(self, doc_type, doc_id, writer=None):
        unique_id = self._create_unique_id(doc_type, doc_id)
        self.log.debug('Removing document from the index: %s', unique_id)
        is_local_writer = False
        if writer is None:
            is_local_writer = True
            writer = self._create_writer()
        try:
            writer.delete_by_term(UNIQUE_ID, unique_id)
            if is_local_writer:
                writer.commit()
        except:
            if is_local_writer:
                writer.cancel()
            raise


    def optimize(self):
        writer = AsyncWriter(self.index)
        writer.commit(optimize=True)

    def commit(self, optimize, writer):
        writer.commit(optimize=optimize)

    def cancel(self, writer):
        try:
            writer.cancel()
        except Exception, ex:
            self.env.log.error("Error during writer cancellation: %s", ex)

    def recreate_index(self):
        self.log.info('Creating Whoosh index in %s' % self.index_dir)
        self._make_dir_if_not_exists()
        return whoosh.index.create_in(self.index_dir, schema=self.SCHEMA)

    def _open_or_create_index_if_missing(self):
        if whoosh.index.exists_in(self.index_dir):
            return whoosh.index.open_dir(self.index_dir)
        else:
            return self.recreate_index()

    def query(self,
              query,
              sort = None,
              fields = None,
              boost = None,
              filter = None,
              facets = None,
              pagenum = 1,
              pagelen = 20):
        """
        Perform query.

        Temporary fixes:
        Whoosh 2.4 raises an error when simultaneously using filters and facets
        in search:
            AttributeError: 'FacetCollector' object has no attribute 'offset'
        The problem should be fixed in the next release. For more info read
        https://bitbucket.org/mchaput/whoosh/issue/274
        A workaround is introduced to join query and filter in query and not
        using filter parameter. Remove the workaround when the fixed version
        of Whoosh is applied.
        """
        with self.index.searcher() as searcher:
            sortedby = self._prepare_sortedby(sort)

            #TODO: investigate how faceting is applied to multi-value fields
            #e.g. keywords. For now, just pass facets lit to Whoosh API
            #groupedby = self._prepare_groupedby(facets)
            groupedby = facets

            #workaround of Whoosh bug, read method __doc__
            query = self._workaround_join_query_and_filter(
                query,
                filter)

            query_parameters = dict(
                query = query,
                pagenum = pagenum,
                pagelen = pagelen,
                sortedby = sortedby,
                groupedby = groupedby,
                maptype=whoosh.sorting.Count,
                #workaround of Whoosh bug, read method __doc__
                #filter = filter,
            )
            self.env.log.debug("Whoosh query to execute: %s",
                query_parameters)
            raw_page = searcher.search_page(**query_parameters)
            results = self._process_results(raw_page, fields, query_parameters)
        return results

    def _workaround_join_query_and_filter(
            self,
            query_expression,
            query_filter):
        if not query_filter:
            return query_expression
        return whoosh.query.And((query_expression, query_filter))

    def _create_unique_id(self, doc_type, doc_id):
        return u"%s:%s" % (doc_type, doc_id)

    def _to_whoosh_format(self, value):
        if isinstance(value, basestring):
            value = unicode(value)
        elif isinstance(value, datetime):
            value = self._convert_date_to_tz_naive_utc(value)
        return value

    def _convert_date_to_tz_naive_utc(self, value):
        """Convert datetime to naive utc datetime
        Whoosh can not read  from index datetime values passed from Trac with
        tzinfo=trac.util.datefmt.FixedOffset because of non-empty
        constructor of FixedOffset"""
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
        groupedby = whoosh.sorting.Facets()
        for facet_name in facets:
            groupedby.add_field(
                facet_name,
                allow_overlap=True,
                maptype=whoosh.sortingwhoosh.Count)
        return groupedby

    def _prepare_sortedby(self, sort):
        if not sort:
            return None
        sortedby = []
        for (field, order) in sort:
            if field.lower() == SCORE:
                if self._is_desc(order):
                    #We can implement tis later by our own ScoreFacet with
                    # "score DESC" support
                    raise TracError(
                        "Whoosh does not support DESC score ordering.")
                sort_condition = whoosh.sorting.ScoreFacet()
            else:
                sort_condition = whoosh.sorting.FieldFacet(
                    field,
                    reverse=self._is_desc(order))
            sortedby.append(sort_condition)
        return sortedby

    def _is_desc(self, order):
        return (order.lower()==DESC)

    def _process_results(self, page, fields, search_parameters = None):
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
        for retrieved_record in page:
            result_doc = self._process_record(fields, retrieved_record)
            docs.append(result_doc)
        results.docs = docs
        results.debug["search_parameters"] = search_parameters
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
        """This method can be also used by unit-tests"""
        non_paged_results = page.results
        facet_names = non_paged_results.facet_names()
        if not facet_names:
            return None
        facets_result = dict()
        for name in facet_names:
            facets_result[name] = non_paged_results.groups(name)
        return facets_result

    def _make_dir_if_not_exists(self):
        if not os.path.exists(self.index_dir):
            os.mkdir(self.index_dir)

        if not os.access(self.index_dir, os.W_OK):
            raise TracError(
                "The path to Whoosh index '%s' is not writable for the\
                 current user."
                % self.index_dir)


class WhooshEmptyFacetErrorWorkaround(Component):
    """
        Whoosh 2.4.1 raises "IndexError: list index out of range"
        when search contains facets on field that is missing in at least one
        document in the index. The error manifests only when index contains
        more than one segment.

        The goal of this class is to temporary solve the problem for
        prototype phase. Fro non-prototype phase, the problem should be solved
        by the next version of Whoosh.

        Remove this class when fixed version of Whoosh is introduced.
    """
    implements(IDocIndexPreprocessor)
    implements(IResultPostprocessor)
    implements(IQueryPreprocessor)

    NULL_MARKER = u"empty"

    should_not_be_empty_fields = [
        IndexFields.STATUS,
        IndexFields.MILESTONE,
        IndexFields.COMPONENT,
    ]

    #IDocIndexPreprocessor methods
    def pre_process(self, doc):
        for field in self.should_not_be_empty_fields:
            if field not in doc or doc[field] is None or doc[field] == empty:
                doc[field] = self.NULL_MARKER

    #IResultPostprocessor methods
    def post_process(self, query_result):
        #fix facets
        if query_result.facets:
            for count_dict in query_result.facets.values():
                for field, count in count_dict.iteritems():
                    if field == self.NULL_MARKER:
                        count_dict[None] = count
                        del count_dict[self.NULL_MARKER]
        #we can fix query_result.docs later if needed

    #IQueryPreprocessor methods
    def query_pre_process(self, query_parameters):
        """
        Go through filter queries and replace "NOT (field_name:*)" query with
        "field_name:NULL_MARKER" query.

        This is really quick fix to make prototype working with hope that
        the next Whoosh version will be released soon.
        """
        if "filter" in query_parameters and query_parameters["filter"]:
            self._find_and_fix_condition(query_parameters["filter"])
        if "query" in query_parameters and query_parameters["query"]:
            self._find_and_fix_condition(query_parameters["query"])

    def _find_and_fix_condition(self, filter_condition):
        if isinstance(filter_condition, whoosh.query.CompoundQuery):
            sub_queries = list(filter_condition.subqueries)
            for i, subquery in enumerate(sub_queries):
                term_to_replace =  self._find_and_fix_condition(subquery)
                if term_to_replace:
                    filter_condition.subqueries[i] = term_to_replace
        elif isinstance(filter_condition, whoosh.query.Not):
            not_query = filter_condition.query
            if isinstance(not_query, whoosh.query.Every) and \
               not_query.fieldname in self.should_not_be_empty_fields:
                return whoosh.query.Term(not_query.fieldname, self.NULL_MARKER)
        return None
