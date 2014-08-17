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

"""
Module providing an implementation of the bhsearch.api.ISearchBackend
interface, suitable for use with Apache Solr.
"""

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

    """Class for implementing the ISearchBackend interface.

    Define the ISearchBackend methods, so that these methods can be
    appropriately used for communicating with the Solr server (via
    Sunburnt).

    Class Attributes:
    UNIQUE_ID -- the field to be used for distinguishing between
    searchable objects
    HIGHLIGHTABLE_FIELDS -- the fields that can be highlighted in
    search results
    server_url -- Option object for adding a new configuration option
    (that lets the user set the Solr server URL) to the trac.ini
    configuration file

    Instance Attributes:
    solr_interface -- a SolrInterface object for communicating with the
    Solr server through Sunburnt
    """

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
        """Initialise a SolrInterface object.

        Initialise the SolrInterface object with the Solr server
        URL provided in trac.ini.
        """

        self.solr_interface = SolrInterface(str(self.server_url))

    def add_doc(self, doc, operation_context=None):
        """Add a new document to the Solr index.

        The contents should be a dict with fields matching the search
        schema. The only required fields are type and id, everything
        else is optional.

        Keyword Arguments:
        doc -- the document to be added
        operation_context -- required by the ISearchBackend API
        (default None)
        """

        self._reformat_doc(doc)
        # Create a unique ID for distinguishing between the searchable
        # objects.
        doc[self.UNIQUE_ID] = self._create_unique_id(doc.get("product", ''),
                                                     doc["type"], doc["id"])
        self.solr_interface.add(doc)
        self.solr_interface.commit()

    def delete_doc(self, product, doc_type, doc_id, operation_context=None):
        """Delete a document from the Solr index.

        The product, type and ID of the document must be provided.

        Keyword Arguments:
        product -- the product associated with the searchable object
        doc_type -- the type of the searchable object
        doc_id -- the ID of the searchable object
        operation_context -- required by the ISearchBackend API
        (default None)
        """

        unique_id = self._create_unique_id(product, doc_type, doc_id)
        self.solr_interface.delete(unique_id)

    def optimize(self):
        """Optimise the Solr index."""
        self.solr_interface.optimize()

    def query(
            self, query, query_string, sort = None, fields = None,
            filter = None, facets = None, pagenum = 1, pagelen = 20,
            highlight = False, highlight_fields = None, context = None):
        """Process the query to be made to the Solr server.

        Create a query chain, and execute the query to the Solr server.
        Return the results, the More Like This results and their
        associated hexdigests.

        Keyword Arguments:
        query -- a whoosh.Query object holding the parsed query
        query_string -- the original query string
        sort -- a list of SortInstruction objects (default None)
        fields -- a list of fields to select (default None)
        filter -- a filter query object (default None)
        facets -- a list of facet fields (default None)
        pagenum -- the number of pages (default 1)
        pagelen -- the maximum page length (default 20)
        highlight -- highlight matched terms in field (default False)
        highlight_fields -- a list of fields to highlight
        (default None)
        context -- required by the ISearchBackend API
        (default None)
        """

        if not query_string:
            query_string = "*.*"

        # Create the query chain to be queried against Solr.
        final_query_chain = self._create_query_chain(query_string)
        solr_query = self.solr_interface.query(final_query_chain)
        faceted_solr_query = solr_query.facet_by(facets)
        highlighted_solr_query = faceted_solr_query.highlight(
                                    self.HIGHLIGHTABLE_FIELDS)

        start = 0 if pagenum == 1 else pagelen * pagenum
        paginated_solr_query = highlighted_solr_query.paginate(
                            start=start, rows=pagelen)
        results = paginated_solr_query.execute()

        # Process the More Like This results for the original query.
        mlt, hexdigests = self.query_more_like_this(paginated_solr_query,
                                                    fields="type", mindf=1,
                                                    mintf=1)

        # Process the query result so that it is compatible with the
        # bhsearch.web_ui internal methods that display the results.
        query_result = self._create_query_result(highlighted_solr_query,
                                                 results, fields, pagenum,
                                                 pagelen)
        return query_result, mlt, hexdigests

    def query_more_like_this(self, query_chain, **kwargs):
        """Retrieve and process More Like These results.

        Execute the query_chain against the Solr server, create a
        hexdigest for each document retrieved (for interface purposes),
        process the result accordingly and return a dictionary
        containing the More Like This results and a dictionary holding
        the hexdigests for each document.

        Keyword Arguments:
        query_chain -- the query chain to be executed to the Solr server
        **kwargs -- remaining keyword arguments
        """

        mlt_results = query_chain.mlt(**kwargs).execute().more_like_these
        mlt_dict = {}
        hexdigests = {}

        for doc, results in mlt_results.iteritems():
            hexdigest = hashlib.md5(doc).hexdigest()
            hexdigests[doc] = hexdigest

            for mlt_doc in results.docs:
                if doc not in mlt_dict:
                    mlt_dict[doc] = [self._process_mlt_doc(mlt_doc)]
                else:
                    mlt_dict[doc].append(self._process_mlt_doc(mlt_doc))

        return mlt_dict, hexdigests

    def _process_mlt_doc(self, doc):
        """Build a dictionary containing required details for the doc.

        Store the required field values for the doc and return this
        dictionary.

        Keyword Arguments:
        doc -- a SolrResult object holding the document's details
        """

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
        """Create a QueryResult object with the retrieved results.

        Keyword Arguments:
        query -- a whoosh.Query object holding the parsed query
        results -- a SolrResponse object holding the retrieve results
        fields -- a list of fields to select
        pagenum -- the number of pages
        pagelen -- the maximum page length
        """

        total_num, total_page_count, page_num, offset = \
                    self._prepare_query_result_attributes(query, pagenum,
                                                          pagelen)

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

    def _create_query_chain(self, query_string):
        """Create the final query chain.

        For each token in the query string, create a query with the
        token against each field. Concatenate all created queries, and
        return the final query chain.

        Keyword Arguments:
        query_string -- the original query string
        """

        # Match the regex against the query string, in order to find
        # all the words in the query.
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
        """Process attributes for the retrieved document or record.

        Create a dictionary holding all fields with their retrieved
        value from the record.

        Keyword Arguments:
        retrieved_record -- a dictionary holding the retrieved record's
        attributes
        fields -- a list of fields to select
        """

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
        """Find the timezone for the datetime instance."""
        if isinstance(value, datetime):
            value = utc.localize(value)
        return value

    def _prepare_query_result_attributes(self, query, pagenum, pagelen):
        """Prepare the QueryResult attributes.

        Prepare the attributes needed for creating a QueryResult object.

        Keyword Arguments:
        query -- the query to be executed against Solr
        pagenum -- the number of pages
        pagelen -- the maximum number of results per page
        """

        results_total_num = query.execute().result.numFound
        total_page_count = int(ceil(results_total_num / pagelen))
        pagenum = min(total_page_count, pagenum)

        offset = (pagenum-1) * pagelen
        if (offset+pagelen) > results_total_num:
            pagelen = results_total_num - offset

        return results_total_num, total_page_count, pagenum, offset

    def is_index_outdated(self):
        # Not applicable to SolrBackend.
        return False

    def recreate_index(self):
        # This method is replaced by the trac-admin command to generate
        # a Solr schema.
        return True

    @contextmanager
    def start_operation(self):
        yield

    def _search_fields_for_token(self, token):
        """Create a query chain for each field.

        For each field, create a query chain querying for the token.

        Keyword Arguments:
        token -- a String holding the current token
        """

        q_chain = None
        field_boosts = DefaultQueryParser(self.env).field_boosts

        for field, boost in field_boosts.iteritems():
            field_token_dict = {field: token}
            if q_chain is None:
                q_chain = self.solr_interface.Q(**field_token_dict)**boost
            else:
                q_chain |= self.solr_interface.Q(**field_token_dict)**boost

        return q_chain

    def _reformat_doc(self, doc):
        # Needed for compatibility with bhsearch
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
        # Needed for compatibility with bhsearch
        if isinstance(value, basestring):
            value = unicode(value)
        elif isinstance(value, datetime):
            value = self._convert_date_to_tz_naive_utc(value)
        return value

    def _convert_date_to_tz_naive_utc(self, value):
        # Needed for compatibility with bhsearch
        if value.tzinfo:
            utc_time = value.astimezone(utc)
            value = utc_time.replace(tzinfo=None)
        return value

    def _create_unique_id(self, product, doc_type, doc_id):
        """Create a unique ID for the doc."""
        if product:
            return u"%s:%s:%s" % (product, doc_type, doc_id)
        else:
            return u"%s:%s" % (doc_type, doc_id)



