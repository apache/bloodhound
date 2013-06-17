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
from trac.config import ExtensionOption, OrderedExtensionsOption
from trac.core import (Interface, Component, ExtensionPoint, TracError,
    implements)
from trac.env import IEnvironmentSetupParticipant
from multiproduct.api import ISupportMultiProductEnvironment
from multiproduct.core import MultiProductExtensionPoint

ASC = "asc"
DESC = "desc"
SCORE = "score"

class IndexFields(object):
    TYPE = "type"
    ID = "id"
    TIME = 'time'
    AUTHOR = 'author'
    CONTENT = 'content'
    STATUS = 'status'
    PRODUCT = 'product'
    REQUIRED_PERMISSION = 'required_permission'
    NAME = 'name'

class QueryResult(object):
    def __init__(self):
        self.hits = 0
        self.page_count = 0
        self.page_number = 0
        self.offset = 0
        self.docs = []
        self.highlighting = []
        self.facets = None
        self.query_suggestion = None
        self.debug = {}

class SortInstruction(object):
    def __init__(self, field, order):
        self.field = field
        self.order = self._parse_sort_order(order)

    def _parse_sort_order(self, order):
        if not order:
            return ASC
        order = order.strip().lower()
        if order == ASC:
            return ASC
        elif order == DESC:
            return DESC
        else:
            raise TracError(
                "Invalid sort order %s in sort instruction" % order)

    def build_sort_expression(self):
        return "%s %s" % (self.field, self.order)

    def __str__(self):
        return str(self.__dict__)

    def __eq__(self, other):
        if not isinstance(other, SortInstruction):
            return False
        return self.__dict__ == other.__dict__


class ISearchWikiSyntaxFormatter(Interface):
    """Extension point interface for wiki syntax processing.
    """

    def format(self, wiki_text):
        """
        Process wiki syntax and return text representation suitable for search
        """

class ISearchBackend(Interface):
    """Extension point interface for search backend systems.
    """

    def add_doc(doc, operation_context):
        """
        Called when new document instance must be added
        """

    def delete_doc(product, doc_type, doc_id, operation_context):
        """
        Delete document from index
        """

    def optimize():
        """
        Optimize index if needed
        """

    def is_index_outdated():
        """
        Check if index is outdated and needs to be recreated.
        """

    def recreate_index():
        """
        Create a new index, if index exists, it will be deleted
        """

    def open_or_create_index_if_missing():
        """
        Open existing index, if index does not exist, create new one
        """

    def query(
            query,
            sort = None,
            fields = None,
            filter = None,
            facets = None,
            pagenum = 1,
            pagelen = 20,
            highlight=False,
            highlight_fields=None,
            context=None):
        """
        Perform query implementation

        :param query: Parsed query object
        :param sort: list of SortInstruction objects
        :param fields: list of fields to select
        :param boost: list of fields with boost values
        :param filter: filter query object
        :param facets: list of facet fields
        :param pagenum: page number
        :param pagelen: page length
        :param highlight: highlight matched terms in fields
        :param highlight_fields: list of fields to highlight
        :return: ResultsPage
        """

    def start_operation(self):
        """Used to get arguments for batch operation withing single commit"""

class IIndexParticipant(Interface):
    """Extension point interface for components that should be searched.
    """

    def get_entries_for_index():
        """List entities for index creation"""

class ISearchParticipant(Interface):
    """Extension point interface for components that should be searched.
    """
    def format_search_results(contents):
        """Called to see if the module wants to format the search results."""

    def is_allowed(req):
        """Called when we want to build the list of components with search.
        Passes the request object to do permission checking."""

    def get_participant_type():
        """Return type of search participant"""

    def get_required_permission(self):
        """Return permission required to view components in search results"""

    def get_title():
        """Return resource title."""

    def get_default_facets():
        """Return default facets for the specific resource type."""

    def get_default_view():
        """Return True if grid is enabled by default for specific resource."""

    def get_default_view_fields(view):
        """Return list of fields should be returned in grid by default."""


class IQueryParser(Interface):
    """Extension point for Bloodhound Search query parser.
    """

    def parse(query_string, context):
        """Parse query from string"""

    def parse_filters(filters):
        """Parse query filters"""

class IDocIndexPreprocessor(Interface):
    """Extension point for Bloodhound Search document pre-processing before
    adding or update documents into index.
    """

    def pre_process(doc):
        """Process document"""

class IResultPostprocessor(Interface):
    """Extension point for Bloodhound Search result post-processing before
    returning result to caller.
    """

    def post_process(query_result):
        """Process document"""

class IQueryPreprocessor(Interface):
    """Extension point for Bloodhound Search query pre processing.
    """

    def query_pre_process(query_parameters, context):
        """Process query parameters"""


class IMetaKeywordParser(Interface):
    """Extension point for custom meta keywords."""

    def match(text, context):
        """If text matches the keyword, return its transformed value."""


class BloodhoundSearchApi(Component):
    """Implements core indexing functionality, provides methods for
    searching, adding and deleting documents from index.
    """
    implements(IEnvironmentSetupParticipant, ISupportMultiProductEnvironment)

    backend = ExtensionOption('bhsearch', 'search_backend',
        ISearchBackend, 'WhooshBackend',
        'Name of the component implementing Bloodhound Search backend \
        interface: ISearchBackend.')

    parser = ExtensionOption('bhsearch', 'query_parser',
        IQueryParser, 'DefaultQueryParser',
        'Name of the component implementing Bloodhound Search query \
        parser.')

    index_pre_processors = OrderedExtensionsOption(
        'bhsearch', 'index_preprocessors', IDocIndexPreprocessor,
        ['SecurityPreprocessor'],
    )
    result_post_processors = ExtensionPoint(IResultPostprocessor)
    query_processors = ExtensionPoint(IQueryPreprocessor)

    index_participants = MultiProductExtensionPoint(IIndexParticipant)

    def query(
            self,
            query,
            sort = None,
            fields = None,
            filter = None,
            facets = None,
            pagenum = 1,
            pagelen = 20,
            highlight = False,
            highlight_fields = None,
            context = None):
        """Return query result from an underlying search backend.

        Arguments:
        :param query: query string e.g. “bla status:closed” or a parsed
            representation of the query.
        :param sort: optional sorting
        :param boost: optional list of fields with boost values e.g.
            {“id”: 1000, “subject” :100, “description”:10}.
        :param filter: optional list of terms. Usually can be cached by
            underlying search framework. For example {“type”: “wiki”}
        :param facets: optional list of facet terms, can be field or expression
        :param page: paging support
        :param pagelen: paging support
        :param highlight: highlight matched terms in fields
        :param highlight_fields: list of fields to highlight
        :param context: request context

        :return: result QueryResult
        """
        # pylint: disable=too-many-locals
        self.env.log.debug("Receive query request: %s", locals())

        parsed_query = self.parser.parse(query, context)

        parsed_filters = self.parser.parse_filters(filter)
        # TODO: add query parsers and meta keywords post-parsing

        # TODO: apply security filters

        query_parameters = dict(
            query = parsed_query,
            query_string = query,
            sort = sort,
            fields = fields,
            filter = parsed_filters,
            facets = facets,
            pagenum = pagenum,
            pagelen = pagelen,
            highlight = highlight,
            highlight_fields = highlight_fields,
        )
        for query_processor in self.query_processors:
            query_processor.query_pre_process(query_parameters, context)

        query_result = self.backend.query(**query_parameters)

        for post_processor in self.result_post_processors:
            post_processor.post_process(query_result)

        query_result.debug["api_parameters"] = query_parameters
        return query_result

    def start_operation(self):
        return self.backend.start_operation()

    def rebuild_index(self):
        """Rebuild underlying index"""
        self.log.info('Rebuilding the search index.')
        self.backend.recreate_index()
        with self.backend.start_operation() as operation_context:
            doc = None
            try:
                for participant in self.index_participants:
                    self.log.info(
                        "Reindexing resources provided by %s in product %s" %
                        (participant.__class__.__name__,
                         getattr(participant.env.product, 'name', "''"))
                    )
                    docs = participant.get_entries_for_index()
                    for doc in docs:
                        self.log.debug(
                            "Indexing document %s:%s/%s" % (
                                doc['product'],
                                doc['type'],
                                doc['id'],
                            )
                        )
                        self.add_doc(doc, operation_context)
                self.log.info("Reindexing complete.")
            except Exception, ex:
                self.log.error(ex)
                if doc:
                    self.log.error("Doc that triggers the error: %s" % doc)
                raise

    def change_doc_id(self, doc, old_id, operation_context=None):
        if operation_context is None:
            with self.backend.start_operation() as operation_context:
                self._change_doc_id(doc, old_id, operation_context)
        else:
            self._change_doc_id(doc, old_id, operation_context)

    def _change_doc_id(self, doc, old_id, operation_context):
        self.backend.delete_doc(
            doc[IndexFields.PRODUCT],
            doc[IndexFields.TYPE],
            old_id,
            operation_context
        )
        self.add_doc(doc, operation_context)


    def optimize(self):
        """Optimize underlying index"""
        self.backend.optimize()

    def add_doc(self, doc, operation_context = None):
        """Add a document to underlying search backend.
        The doc must be dictionary with obligatory "type" field
        """
        for preprocessor in self.index_pre_processors:
            preprocessor.pre_process(doc)
        self.backend.add_doc(doc, operation_context)

    def delete_doc(self, product, doc_type, doc_id):
        """Delete the document from underlying search backend.
        """
        self.backend.delete_doc(product, doc_type, doc_id)

    # IEnvironmentSetupParticipant methods

    def environment_created(self):
        self.upgrade_environment(self.env.db_transaction)

    def environment_needs_upgrade(self, db):
        # pylint: disable=unused-argument
        return self.backend.is_index_outdated()

    def upgrade_environment(self, db):
        # pylint: disable=unused-argument
        self.rebuild_index()
