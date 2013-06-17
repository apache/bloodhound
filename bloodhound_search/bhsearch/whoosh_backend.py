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
from bhsearch import BHSEARCH_CONFIG_SECTION
from bhsearch.api import ISearchBackend, DESC, QueryResult, SCORE, \
    IDocIndexPreprocessor, IResultPostprocessor, IndexFields, \
    IQueryPreprocessor
import os
from bhsearch.search_resources.ticket_search import TicketFields
from bhsearch.security import SecurityPreprocessor
from bhsearch.utils import get_global_env
from trac.core import Component, implements, TracError
from trac.config import Option, IntOption
from trac.util.text import empty
from trac.util.datefmt import utc
from whoosh.fields import Schema, ID, DATETIME, KEYWORD, TEXT
from whoosh import index, analysis
import whoosh
import whoosh.highlight
from whoosh.collectors import FilterCollector
from whoosh.writing import AsyncWriter
from datetime import datetime

from bhsearch.whoosh_fixes import fixes_for
for fix in fixes_for(whoosh.__version__):
    apply(fix)

UNIQUE_ID = "unique_id"


class WhooshBackend(Component):
    """
    Implements Whoosh SearchBackend interface
    """
    implements(ISearchBackend)

    index_dir_setting = Option(
        BHSEARCH_CONFIG_SECTION,
        'whoosh_index_dir',
        default='whoosh_index',
        doc="""Relative path is resolved relatively to the
        directory of the environment.""")

    advanced_security = Option(
        BHSEARCH_CONFIG_SECTION,
        'advanced_security',
        default=False,
        doc="Check view permission for each document when retrieving results."
    )

    max_fragment_size = IntOption(
        BHSEARCH_CONFIG_SECTION,
        'max_fragment_size',
        default=240,
        doc="The maximum number of characters allowed in a fragment.")

    fragment_surround = IntOption(
        BHSEARCH_CONFIG_SECTION,
        'fragment_surround',
        default=60,
        doc="""The number of extra characters of context to add both before
        the first matched term and after the last matched term.""")

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
        summary=TEXT(stored=True,
                     analyzer=analysis.StandardAnalyzer(stoplist=None)),
        content=TEXT(stored=True,
                     analyzer=analysis.StandardAnalyzer(stoplist=None)),
        changes=TEXT(analyzer=analysis.StandardAnalyzer(stoplist=None)),
        owner=TEXT(stored=True,
                   analyzer=analysis.SimpleAnalyzer()),
        repository=TEXT(stored=True,
                        analyzer=analysis.SimpleAnalyzer()),
        revision=TEXT(stored=True,
                      analyzer=analysis.SimpleAnalyzer()),
        message=TEXT(stored=True,
                     analyzer=analysis.SimpleAnalyzer()),
        required_permission=ID(),
        name=TEXT(stored=True,
                  analyzer=analysis.SimpleAnalyzer()),
        query_suggestion_basket=TEXT(analyzer=analysis.SimpleAnalyzer(),
                                     spelling=True),
        relations=KEYWORD(lowercase=True, commas=True),
    )

    def __init__(self):
        self.index_dir = self.index_dir_setting
        if not os.path.isabs(self.index_dir):
            self.index_dir = os.path.join(get_global_env(self.env).path,
                                          self.index_dir)
        if index.exists_in(self.index_dir):
            self.index = index.open_dir(self.index_dir)
        else:
            self.index = None

    #ISearchBackend methods
    def start_operation(self):
        return self._create_writer()

    def _create_writer(self):
        return AsyncWriter(self.index)

    def add_doc(self, doc, operation_context=None):
        """Add any type of  document index.

        The contents should be a dict with fields matching the search schema.
        The only required fields are type and id, everything else is optional.
        """
        writer = operation_context
        is_local_writer = False
        if writer is None:
            is_local_writer = True
            writer = self._create_writer()

        self._reformat_doc(doc)
        doc[UNIQUE_ID] = self._create_unique_id(doc.get("product", ''),
                                                doc["type"],
                                                doc["id"])
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

    def delete_doc(self, product, doc_type, doc_id, operation_context=None):
        unique_id = self._create_unique_id(product, doc_type, doc_id)
        self.log.debug('Removing document from the index: %s', unique_id)
        writer = operation_context
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

    def is_index_outdated(self):
        return self.index is None or not self.index.schema == self.SCHEMA

    def recreate_index(self):
        self.log.info('Creating Whoosh index in %s' % self.index_dir)
        self._make_dir_if_not_exists()
        self.index = index.create_in(self.index_dir, schema=self.SCHEMA)
        return self.index

    def query(self,
              query,
              query_string=None,
              sort = None,
              fields = None,
              filter = None,
              facets = None,
              pagenum = 1,
              pagelen = 20,
              highlight = False,
              highlight_fields = None,
              context=None):
        # pylint: disable=too-many-locals
        with self.index.searcher() as searcher:
            self._apply_advanced_security(searcher, context)

            highlight_fields = self._prepare_highlight_fields(highlight,
                                                              highlight_fields)

            sortedby = self._prepare_sortedby(sort)

            #TODO: investigate how faceting is applied to multi-value fields
            #e.g. keywords. For now, just pass facets lit to Whoosh API
            #groupedby = self._prepare_groupedby(facets)
            groupedby = facets

            query_parameters = dict(
                query = query,
                pagenum = pagenum,
                pagelen = pagelen,
                sortedby = sortedby,
                groupedby = groupedby,
                maptype=whoosh.sorting.Count,
                filter = filter,
            )
            self.env.log.debug("Whoosh query to execute: %s",
                query_parameters)
            raw_page = searcher.search_page(**query_parameters)
            results = self._process_results(raw_page,
                                            fields,
                                            highlight_fields,
                                            query_parameters)
            if query_string is not None:
                c = searcher.correct_query(query, query_string)
                results.query_suggestion = c.string
            try:
                actual_query = unicode(query.simplify(searcher))
                results.debug['actual_query'] = actual_query
            # pylint: disable=bare-except
            except:
                # Simplify has a bug that causes it to fail sometimes.
                pass
        return results

    def _apply_advanced_security(self, searcher, context=None):
        if not self.advanced_security:
            return

        old_collector = searcher.collector
        security_processor = SecurityPreprocessor(self.env)

        def check_permission(doc):
            return security_processor.check_permission(doc, context)

        def collector(*args, **kwargs):
            c = old_collector(*args, **kwargs)
            if isinstance(c, FilterCollector):
                c = AdvancedFilterCollector(
                    c.child, c.allow, c.restrict, check_permission
                )
            else:
                c = AdvancedFilterCollector(
                    c, None, None, check_permission
                )
            return c
        searcher.collector = collector

    def _create_unique_id(self, product, doc_type, doc_id):
        product, doc_type, doc_id = \
            self._apply_empty_facets_workaround(product, doc_type, doc_id)

        if product:
            return u"%s:%s:%s" % (product, doc_type, doc_id)
        else:
            return u"%s:%s" % (doc_type, doc_id)

    def _apply_empty_facets_workaround(self, product, doc_type, doc_id):
        # Apply the same workaround that is used at insertion time
        doc = {
            IndexFields.PRODUCT: product,
            IndexFields.TYPE: doc_type,
            IndexFields.ID: doc_id,
        }
        WhooshEmptyFacetErrorWorkaround(self.env).pre_process(doc)
        return (doc[IndexFields.PRODUCT],
                doc[IndexFields.TYPE],
                doc[IndexFields.ID])

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
        for sort_instruction in sort:
            field = sort_instruction.field
            order = sort_instruction.order
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

    def _prepare_highlight_fields(self, highlight, highlight_fields):
        if not highlight:
            return ()

        if not highlight_fields:
            highlight_fields = self._all_highlightable_fields()

        return highlight_fields

    def _all_highlightable_fields(self):
        return [name for name, field in self.SCHEMA.items()
                if self._is_highlightable(field)]

    def _is_highlightable(self, field):
        return not isinstance(field, whoosh.fields.DATETIME) and field.stored

    def _is_desc(self, order):
        return (order.lower()==DESC)

    def _process_results(self,
                         page,
                         fields,
                         highlight_fields,
                         search_parameters=None):
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
        highlighting = []
        for retrieved_record in page:
            result_doc = self._process_record(fields, retrieved_record)
            docs.append(result_doc)

            result_highlights = self._create_highlights(highlight_fields,
                                                        retrieved_record)
            highlighting.append(result_highlights)
        results.docs = docs
        results.highlighting = highlighting

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

    def _create_highlights(self, fields, record):
        result_highlights = dict()
        fragmenter = whoosh.highlight.ContextFragmenter(
            self.max_fragment_size,
            self.fragment_surround,
        )
        highlighter = whoosh.highlight.Highlighter(
            formatter=WhooshEmFormatter(),
            fragmenter=fragmenter)

        for field in fields:
            if field in record:
                highlighted = highlighter.highlight_hit(record, field)
            else:
                highlighted = ''
            result_highlights[field] = highlighted
        return result_highlights


class WhooshEmFormatter(whoosh.highlight.HtmlFormatter):
    template = '<em>%(t)s</em>'


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
        TicketFields.MILESTONE,
        TicketFields.COMPONENT,
        IndexFields.PRODUCT,
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

        #fix query_result.docs
        for doc in query_result.docs:
            for field, value in doc.items():
                if value == self.NULL_MARKER:
                    del doc[field]

    #IQueryPreprocessor methods
    def query_pre_process(self, query_parameters, context=None):
        """
        Go through filter queries and replace "NOT (field_name:*)" query with
        "field_name:NULL_MARKER" query.

        This is really quick fix to make prototype working with hope that
        the next Whoosh version will be released soon.
        """
        # pylint: disable=unused-argument
        if "filter" in query_parameters and query_parameters["filter"]:
            term_to_replace = \
                self._find_and_fix_condition(query_parameters["filter"])
            if term_to_replace:
                query_parameters["filter"] = term_to_replace
        if "query" in query_parameters and query_parameters["query"]:
            term_to_replace = \
                self._find_and_fix_condition(query_parameters["query"])
            if term_to_replace:
                query_parameters["query"] = term_to_replace

    def _find_and_fix_condition(self, filter_condition):
        if isinstance(filter_condition, whoosh.query.CompoundQuery):
            sub_queries = list(filter_condition.subqueries)
            for i, subquery in enumerate(sub_queries):
                term_to_replace = self._find_and_fix_condition(subquery)
                if term_to_replace:
                    filter_condition.subqueries[i] = term_to_replace
        elif isinstance(filter_condition, whoosh.query.Not):
            not_query = filter_condition.query
            if isinstance(not_query, whoosh.query.Every) and \
               not_query.fieldname in self.should_not_be_empty_fields:
                return whoosh.query.Term(not_query.fieldname, self.NULL_MARKER)
        return None


class AdvancedFilterCollector(FilterCollector):
    """An advanced filter collector, accepting a callback function that
    will be called for each document to determine whether it should be
    filtered out or not.

    Please note that it can be slow. Very slow.
    """

    def __init__(self, child, allow, restrict, filter_func=None):
        FilterCollector.__init__(self, child, allow, restrict)
        self.filter_func = filter_func

    def collect_matches(self):
        child = self.child
        _allow = self._allow
        _restrict = self._restrict

        if _allow is not None or _restrict is not None:
            filtered_count = self.filtered_count
            for sub_docnum in child.matches():
                global_docnum = self.offset + sub_docnum
                if ((_allow is not None and global_docnum not in _allow)
                    or (_restrict is not None and global_docnum in _restrict)):
                    filtered_count += 1
                    continue

                if self.filter_func:
                    doc = self.subsearcher.stored_fields(sub_docnum)
                    if not self.filter_func(doc):
                        filtered_count += 1
                        continue

                child.collect(sub_docnum)
            # pylint: disable=attribute-defined-outside-init
            self.filtered_count = filtered_count
        else:
            # If there was no allow or restrict set, don't do anything special,
            # just forward the call to the child collector
            child.collect_matches()
