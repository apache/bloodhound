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

import re
import hashlib

from math import ceil
from datetime import datetime
from contextlib import contextmanager
from sunburnt import SolrInterface

from bhsearch import BHSEARCH_CONFIG_SECTION
from bhsearch.api import ISearchBackend, SCORE, QueryResult
from bhsearch.query_parser import DefaultQueryParser
from bhsearch.search_resources.ticket_search import TicketIndexer
from multiproduct.env import ProductEnvironment
from trac.core import Component, implements, TracError
from trac.config import Option
from trac.ticket.model import Ticket
from trac.ticket.api import TicketSystem
from trac.util.datefmt import utc


class SolrBackend(Component):
    implements(ISearchBackend)

    UNIQUE_ID = "unique_id"

    HIGHLIGHTABLE_FIELDS = {
        "unique_id" : True,
        "id" : True,
        "type" : True,
        "product" : True,
        "milestone" : True,
        "author" : True,
        "component" : True,
        "status" : True,
        "resolution" : True,
        "keywords" : True,
        "summary" : True,
        "content" : True,
        "changes" : True,
        "owner" : True,
        "repository" : True,
        "revision" : True,
        "message" : True,
        "name" : True
        }

    server_url = Option(
            BHSEARCH_CONFIG_SECTION,
            'solr_server_url',
            doc="""Url of the server running Solr instance.""",
            doc_domain='bhsearch')

    def __init__(self):
        self.solr_interface = SolrInterface(str(self.server_url))

    def add_doc(self, doc, operation_context=None):
        self._reformat_doc(doc)
        doc[self.UNIQUE_ID] = self._create_unique_id(doc.get("product", ''),
                                                doc["type"], doc["id"])
        self.solr_interface.add(doc)
        self.solr_interface.commit()

    def delete_doc(product, doc_type, doc_id, operation_context=None):
        unique_id = self._create_unique_id(product, doc_type, doc_id)
        self.solr_interface.delete(unique_id)

    def optimize(self):
        self.solr_interface.optimize()

    def query(
            self, query, query_string, sort = None, fields = None,
            filter = None, facets = None, pagenum = 1, pagelen = 20,
            highlight = False, highlight_fields = None, context = None):

        if not query_string:
            query_string = "*.*"

        final_query_chain = self._create_query_chain(query, query_string)
        solr_query = self.solr_interface.query(final_query_chain)
        faceted_solr_query = solr_query.facet_by(facets)
        highlighted_solr_query = faceted_solr_query.highlight(
                                    self.HIGHLIGHTABLE_FIELDS)

        start = 0 if pagenum == 1 else pagelen * pagenum
        paginated_solr_query = highlighted_solr_query.paginate(
                            start=start, rows=pagelen)
        results = paginated_solr_query.execute()

        mlt, hexdigests = self.query_more_like_this(paginated_solr_query,
                                                    fields="type", mindf=1,
                                                    mintf=1)

        query_result = self._create_query_result(highlighted_solr_query,
                                                 results, fields, pagenum,
                                                 pagelen)
        return query_result, mlt, hexdigests

    def query_more_like_this(self, query_chain, **kwargs):
        mlt_results = query_chain.mlt(**kwargs).execute().more_like_these
        mlt_dict = {}
        hexdigests = {}

        for doc, results in mlt_results.iteritems():
            hexdigest = hashlib.md5(doc).hexdigest()
            hexdigests[doc] = hexdigest

            for mlt_doc in results.docs:
                if doc not in mlt_dict:
                    mlt_dict[doc] = [self._process_doc(mlt_doc)]
                else:
                    mlt_dict[doc].append(self._process_doc(mlt_doc))

        return mlt_dict, hexdigests

    def _process_doc(self, doc):
        ui_doc = dict(doc)

        if doc.get('product'):
            env = ProductEnvironment(self.env, doc['product'])
            product_href = ProductEnvironment.resolve_href(env, self.env)
            ui_doc["href"] = product_href(doc['type'], doc['id'])
        else:
            ui_doc["href"] = self.env.href(doc['type'], doc['id'])

        ui_doc['title'] = str(doc['type'] + ": " + doc['_stored_name']).title()

        return ui_doc

    def _create_query_result(
                        self, query, results, fields, pagenum, pagelen):
        total_num, total_page_count, page_num, offset = \
                    self._prepare_query_result_attributes(query, results,
                                                          pagenum, pagelen)

        query_results = QueryResult()
        query_results.hits = total_num
        query_results.total_page_count = total_page_count
        query_results.page_number = page_num
        query_results.offset = offset

        docs = []
        highlighting = []

        for retrieved_record in results:
            result_doc = self._process_record(fields, retrieved_record)
            docs.append(result_doc)

            result_highlights = dict(retrieved_record['solr_highlights'])

            highlighting.append(result_highlights)
            query_results.docs = docs
            query_results.highlighting = highlighting

        return query_results

    def _create_query_chain(self, query, query_string):
        matches = re.findall(re.compile(r'([\w\*]+)'), query_string)
        tokens = set([match for match in matches])

        final_query_chain = None
        for token in tokens:
            token_query_chain = self._search_fields_for_token(token)
            if final_query_chain is None:
                final_query_chain = token_query_chain
            else:
                final_query_chain |= token_query_chain

        return final_query_chain

    def _process_record(self, fields, retrieved_record):
        result_doc = dict()
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

    def _from_whoosh_format(self, value):
        if isinstance(value, datetime):
            value = utc.localize(value)
        return value

    def _prepare_query_result_attributes(
                                    self, query, results, pagenum, pagelen):
        results_total_num = query.execute().result.numFound
        total_page_count = int(ceil(results_total_num / pagelen))
        pagenum = min(total_page_count, pagenum)

        offset = (pagenum-1) * pagelen
        if (offset+pagelen) > results_total_num:
            pagelen = results_total_num - offset

        return results_total_num, total_page_count, pagenum, offset

    def is_index_outdated(self):
        return False

    def recreate_index(self):
        return True

    @contextmanager
    def start_operation(self):
        yield

    def _search_fields_for_token(self, token):
        q_chain = None
        field_boosts = DefaultQueryParser(self.env).field_boosts

        for field, boost in field_boosts.iteritems():
            if field != 'query_suggestion_basket' and field != 'relations':
                field_token_dict = {field: token}
                if q_chain is None:
                    q_chain = self.solr_interface.Q(**field_token_dict)**boost
                else:
                    q_chain |= self.solr_interface.Q(**field_token_dict)**boost

        return q_chain

    def _reformat_doc(self, doc):
        for key, value in doc.items():
            if key is None:
                del doc[None]
            elif value is None:
                del doc[key]
            elif isinstance(value, basestring) and value == "":
                del doc[key]
            else:
                doc[key] = self._to_whoosh_format(value)

    def _to_whoosh_format(self, value):
        if isinstance(value, basestring):
            value = unicode(value)
        elif isinstance(value, datetime):
            value = self._convert_date_to_tz_naive_utc(value)
        return value

    def _convert_date_to_tz_naive_utc(self, value):
        if value.tzinfo:
            utc_time = value.astimezone(utc)
            value = utc_time.replace(tzinfo=None)
        return value

    def _create_unique_id(self, product, doc_type, doc_id):
        if product:
            return u"%s:%s:%s" % (product, doc_type, doc_id)
        else:
            return u"%s:%s" % (doc_type, doc_id)



