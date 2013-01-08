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

r"""Core Bloodhound Search components."""

from trac.core import *
from trac.config import ExtensionOption

ASC = "asc"
DESC = "desc"
SCORE = "score"

class QueryResult(object):
    def __init__(self):
        self.hits = 0
        self.page_count = 0
        self.page_number = 0
        self.offset = 0
        self.docs = []
        self.facets = None


class ISearchBackend(Interface):
    """Extension point interface for search backend systems.
    """

    def add_doc(self, doc, commit=True):
        """
        Called when new document instance must be added

        :param doc: document to add
        :param commit: flag if commit should be automatically called
        """

    def delete_doc(self, doc, commit=True):
        """
        Delete document from index

        :param doc: document to delete
        :param commit: flag if commit should be automatically called
        """

    def commit(self):
        """
        Commits changes
        """

    def optimize(self):
        """
        Optimize index if needed
        """

    def recreate_index(self):
        """
        Create a new index, if index exists, it will be deleted
        """

    def open_or_create_index_if_missing(self):
        """
        Open existing index, if index does not exist, create new one
        """
    def query(self, query, sort = None, fields = None, boost = None, filters = None,
                  facets = None, pagenum = 1, pagelen = 20):
        """
        Perform query implementation

        :param query:
        :param sort:
        :param fields:
        :param boost:
        :param filters:
        :param facets:
        :param pagenum:
        :param pagelen:
        :return: TBD!!!
        """
        pass

class ISearchParticipant(Interface):
    """Extension point interface for components that should be searched.
    """

    def get_search_filters(req):
        """Called when we want to build the list of components with search.
        Passes the request object to do permission checking."""
        pass

    def build_search_index(backend):
        """Called when we want to rebuild the entire index.
        :type backend: ISearchBackend
        """
        pass

    def format_search_results(contents):
        """Called to see if the module wants to format the search results."""

class IQueryParser(Interface):
    """Extension point for Bloodhound Search query parser.
    """

    def parse(query_string, req = None):
        pass

class BloodhoundSearchApi(Component):
    """Implements core indexing functionality, provides methods for
    searching, adding and deleting documents from index.
    """
    backend = ExtensionOption('bhsearch', 'search_backend',
        ISearchBackend, 'WhooshBackend',
        'Name of the component implementing Bloodhound Search backend \
        interface: ISearchBackend.')

    parser = ExtensionOption('bhsearch', 'query_parser',
        IQueryParser, 'DefaultQueryParser',
        'Name of the component implementing Bloodhound Search query \
        parser.')

    search_participants = ExtensionPoint(ISearchParticipant)

    def query(self, query, req = None, sort = None, fields = None, boost = None, filters = None,
                  facets = None, pagenum = 1, pagelen = 20):
        """Return query result from an underlying search backend.

        Arguments:
        :param query: query string e.g. “bla status:closed” or a parsed
            representation of the query.
        :param sort: optional sorting
        :param boost: optional list of fields with boost values e.g.
            {“id”: 1000, “subject” :100, “description”:10}.
        :param filters: optional list of terms. Usually can be cached by underlying
            search framework. For example {“type”: “wiki”}
        :param facets: optional list of facet terms, can be field or expression.
        :param page: paging support
        :param pagelen: paging support

        :return: result QueryResult
        """
        self.env.log.debug("Receive query request: %s", locals())

        # TODO: add query parsers and meta keywords post-parsing

        # TODO: apply security filters

        parsed_query = self.parser.parse(query, req)

        #some backend-independent logic will come here...
        query_result = self.backend.query(
            query = parsed_query,
            sort = sort,
            fields = fields,
            filters = filters,
            facets = facets,
            pagenum = pagenum,
            pagelen = pagelen,
        )

        return query_result


    def rebuild_index(self):
        """Delete the index if it exists. Then create a new full index."""
        self.log.info('Rebuilding the search index.')
        self.backend.recreate_index()

        for participant in self.search_participants:
            participant.build_search_index(self.backend)
        self.backend.commit()
        self.backend.optimize()

        #Erase the index if it exists. Then create a new index from scratch.

        #erase ticket
        #call reindex for each resource
        #commit
        pass

    def optimize(self):
        """Optimize underlying index"""
        pass

    def add_doc(self, doc):
        """Add a document to underlying search backend.

        The doc must be dictionary with obligatory "type" field
        """
        self.backend.add_doc(doc)

    def delete_doc(self, type, id):
        """Add a document from underlying search backend.

        The doc must be dictionary with obligatory "type" field
        """
        pass



