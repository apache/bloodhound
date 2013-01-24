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

r"""Bloodhound Search user interface."""
import copy

import pkg_resources
import re

from trac.core import Component, implements, TracError
from genshi.builder import tag
from trac.perm import IPermissionRequestor
from trac.search import shorten_result
from trac.config import OrderedExtensionsOption, ListOption
from trac.util.presentation import Paginator
from trac.util.datefmt import format_datetime, user_time
from trac.web import IRequestHandler
from trac.util.translation import _
from trac.web.chrome import INavigationContributor, ITemplateProvider, \
                             add_link, add_stylesheet
from bhsearch.api import BloodhoundSearchApi, ISearchParticipant, SCORE, ASC, \
    DESC, IndexFields

SEARCH_PERMISSION = 'SEARCH_VIEW'
DEFAULT_RESULTS_PER_PAGE = 10
DEFAULT_SORT = [(SCORE, ASC), ("time", DESC)]


class RequestParameters(object):
    """
    Helper class for parameter parsing and creation of bhsearch specific URLs.

    Lifecycle of the class must be per request
    """
    QUERY = "q"
    PAGE = "page"
    TYPE = "type"
    NO_QUICK_JUMP = "noquickjump"
    PAGELEN = "pagelen"
    FILTER_QUERY = "fq"

    def __init__(self, req):
        self.req = req

        self.query = req.args.getfirst(RequestParameters.QUERY)
        if self.query == None:
            self.query = ""

        #TODO: add quick jump functionality
        self.noquickjump = 1

        self.filter_queries = req.args.getlist(RequestParameters.FILTER_QUERY)
        self.filter_queries = self._remove_possible_duplications(
                        self.filter_queries)

        #TODO: retrieve sort from query string
        self.sort = DEFAULT_SORT

        self.pagelen = int(req.args.getfirst(
            RequestParameters.PAGELEN,
            DEFAULT_RESULTS_PER_PAGE))
        self.page = int(req.args.getfirst(RequestParameters.PAGE, '1'))
        self.type = req.args.getfirst(RequestParameters.TYPE, None)

        self.params = {
            self.NO_QUICK_JUMP: self.noquickjump,
            RequestParameters.FILTER_QUERY: []
        }
        if self.query:
            self.params[self.QUERY] = self.query
        if self.pagelen != DEFAULT_RESULTS_PER_PAGE:
            self.params[self.PAGELEN] = self.pagelen
        if self.page > 1:
            self.params[self.PAGE] = self.page
        if self.type:
            self.params[self.TYPE] = self.type
        if self.filter_queries:
            self.params[RequestParameters.FILTER_QUERY] = self.filter_queries

    def _remove_possible_duplications(self, parameters_list):
        seen = set()
        return [parameter for parameter in parameters_list
                if parameter not in seen and not seen.add(parameter)]

    def create_href(
            self,
            page = None,
            type=None,
            skip_type = False,
            skip_page = False,
            filter_query = None,
            skip_filter_query = False,
            force_filters = None
            ):
        params = copy.deepcopy(self.params)
        if page:
            params[self.PAGE] = page

        if skip_page and self.PAGE in params:
            del(params[self.PAGE])

        if type:
            params[self.TYPE] = type

        if skip_type and self.TYPE in params:
            del(params[self.TYPE])

        if skip_filter_query:
            params[self.FILTER_QUERY] = []
        elif filter_query and filter_query not in params[self.FILTER_QUERY]:
            params[self.FILTER_QUERY].append(filter_query)
        elif force_filters is not None:
            params[self.FILTER_QUERY] = force_filters

        return self.req.href.bhsearch(**params)

    def is_show_all_mode(self):
        return self.type is None

class BloodhoundSearchModule(Component):
    """Main search page"""

    implements(INavigationContributor, IPermissionRequestor, IRequestHandler,
               ITemplateProvider,
    #           IWikiSyntaxProvider #todo: implement later
    )

    search_participants = OrderedExtensionsOption(
        'bhsearch',
        'search_participants',
        ISearchParticipant,
        "TicketSearchParticipant, WikiSearchParticipant"
    )


    default_facets_all = ListOption('bhsearch', 'default_facets_all',
        doc="""Default facets applied to search through all resources""")


    # INavigationContributor methods
    def get_active_navigation_item(self, req):
        return 'bhsearch'

    def get_navigation_items(self, req):
        if SEARCH_PERMISSION in req.perm:
            yield ('mainnav', 'bhsearch',
                   tag.a(_('Bloodhound Search'), href=self.env.href.bhsearch())
                )

    # IPermissionRequestor methods
    def get_permission_actions(self):
        return [SEARCH_PERMISSION]

    # IRequestHandler methods
    def match_request(self, req):
        return re.match(r'/bhsearch?', req.path_info) is not None

    def process_request(self, req):
        req.perm.assert_permission(SEARCH_PERMISSION)
        parameters = RequestParameters(req)
        query_string = parameters.query

        #TODO add quick jump support

        allowed_participants = self._get_allowed_participants(req)
        data = {
            'query': query_string,
            }
        self._prepare_allowed_types(allowed_participants, parameters, data)
        self._prepare_active_filter_queries(
            parameters,
            data,
        )

        #TBD: should search return results on empty query?
#        if not any((
#            query_string,
#            parameters.type,
#            parameters.filter_queries,
#            )):
#            return self._return_data(req, data)

        query_filter = self._prepare_query_filter(
            parameters,
            allowed_participants)

        facets = self._prepare_facets(parameters, allowed_participants)

        query_system = BloodhoundSearchApi(self.env)
        query_result = query_system.query(
            query_string,
            pagenum=parameters.page,
            pagelen=parameters.pagelen,
            sort=parameters.sort,
            facets=facets,
            filter=query_filter)

        ui_docs = [self._process_doc(doc, req, allowed_participants)
                   for doc in query_result.docs]

        results = Paginator(
            ui_docs,
            parameters.page - 1,
            parameters.pagelen,
            query_result.hits)

        results.shown_pages = self._prepare_shown_pages(
            parameters,
            shown_pages = results.get_shown_pages(parameters.pagelen))

        results.current_page = {'href': None,
                                'class': 'current',
                                'string': str(results.page + 1),
                                'title':None}

        if results.has_next_page:
            next_href = parameters.create_href(page = parameters.page + 1)
            add_link(req, 'next', next_href, _('Next Page'))

        if results.has_previous_page:
            prev_href = parameters.create_href(page = parameters.page - 1)
            add_link(req, 'prev', prev_href, _('Previous Page'))


        data['results'] = results

        self._prepare_result_facet_counts(
            parameters,
            query_result,
            data,
        )

        data['page_href'] = parameters.create_href()
        return self._return_data(req, data)

    def _prepare_allowed_types(self, allowed_participants, parameters, data):
        active_type = parameters.type
        if active_type and active_type not in allowed_participants:
            raise TracError(_("Unsupported resource type: '%(name)s'",
                name=active_type))
        allowed_types = [
            dict(
                label=_("All"),
                active=(active_type is None),
                href=parameters.create_href(
                    skip_type=True,
                    skip_page=True,
                    force_filters=[],
                ),
            )
        ]

        #we want obtain the same order as in search participants options
        participant_with_type = dict((participant, type)
            for type, participant in allowed_participants.iteritems())
        for participant in self.search_participants:
            if participant in participant_with_type:
                type = participant_with_type[participant]
                allowed_types.append(dict(
                    label=_(participant.get_title()),
                    active=(type ==active_type),
                    href=parameters.create_href(
                        type=type,
                        skip_page=True,
                        force_filters=[],
                    ),
                ))
        data["types"] =  allowed_types
        data["active_type"] =  active_type



    def _prepare_active_filter_queries(
            self,
            parameters,
            data):
        active_filter_queries = []
        for filter_query in parameters.filter_queries:
            active_filter_queries.append(dict(
                href=parameters.create_href(
                    force_filters=self._cut_filters(
                        parameters.filter_queries,
                        filter_query)),
                label=filter_query,
                query=filter_query,
            ))
        data['active_filter_queries'] = active_filter_queries

    def _cut_filters(self, filter_queries, filer_to_cut_from):
        return filter_queries[:filter_queries.index(filer_to_cut_from)]


    def _prepare_result_facet_counts(self, parameters, query_result, data):
        """

        Sample query_result.facets content returned by query
        {
           'component': {None:2},
           'milestone': {None:1, 'm1':1},
        }

        returned facet_count contains href parameters:
        {
           'component': {None: {'count':2, href:'...'},
           'milestone': {
                            None: {'count':1,, href:'...'},
                            'm1':{'count':1, href:'...'}
                        },
        }

        """
        result_facets = query_result.facets
        facet_counts = dict()
        if result_facets:
            for field, facets_dict in result_facets.iteritems():
                per_field_dict = dict()
                for field_value, count in facets_dict.iteritems():
                    if field==IndexFields.TYPE:
                        href = parameters.create_href(
                            skip_page=True,
                            skip_filter_query=True,
                            type=field_value)
                    else:
                        href = parameters.create_href(
                            skip_page=True,
                            filter_query=self._create_field_term_expression(
                                field,
                                field_value)
                        )
                    per_field_dict[field_value] = dict(
                        count=count,
                        href=href
                    )
                facet_counts[_(field)] = per_field_dict

        data['facet_counts'] = facet_counts

    def _create_field_term_expression(self, field, field_value):
        if field_value is None:
            query = "NOT (%s:*)" % field
        elif isinstance(field_value, basestring):
            query = '%s:"%s"' % (field, field_value)
        else:
            query = '%s:%s' % (field, field_value)
        return query

    def _prepare_query_filter(self, parameters, allowed_participants):
        query_filters = list(parameters.filter_queries)
        type = parameters.type
        if type in allowed_participants:
            query_filters.append(
                self._create_field_term_expression(IndexFields.TYPE, type))
        else:
            self.log.debug("Unsupported type in web request: %s", type)
        return query_filters

    def _prepare_facets(self, parameters, allowed_participants):
        #TODO: add possibility of specifying facets in query parameters
        if parameters.is_show_all_mode():
            facets = [IndexFields.TYPE]
            facets.extend(self.default_facets_all)
        else:
            type_participant = allowed_participants[parameters.type]
            facets = type_participant.get_default_facets()
        return facets

    def _get_allowed_participants(self, req):
        allowed_participants = {}
        for participant in self.search_participants:
            type = participant.get_search_filters(req)
            if type is not None:
                allowed_participants[type] = participant
        return allowed_participants

    def _return_data(self, req, data):
        add_stylesheet(req, 'common/css/search.css')
        return 'bhsearch.html', data, None

    def _process_doc(self, doc, req, allowed_participants):
        #todo: introduce copy by predefined value
        ui_doc = dict(doc)

        ui_doc["href"] = req.href(doc['type'], doc['id'])
        #todo: perform content adaptation here
        if doc.has_key('content'):
            ui_doc['excerpt'] = shorten_result(doc['content'])
        if doc.has_key('time'):
            ui_doc['date'] = user_time(req, format_datetime, doc['time'])

        ui_doc['title'] = allowed_participants[doc['type']]\
                .format_search_results(doc)
        return ui_doc

    def _prepare_shown_pages(self, parameters, shown_pages):
        page_data = []
        for shown_page in shown_pages:
            page_href = parameters.create_href(page=shown_page)
            page_data.append([page_href, None, str(shown_page),
                             'page ' + str(shown_page)])
        fields = ['href', 'class', 'string', 'title']
        result_shown_pages = [dict(zip(fields, p)) for p in page_data]
        return result_shown_pages


    # ITemplateProvider methods
    def get_htdocs_dirs(self):
#        return [('bhsearch',
#                 pkg_resources.resource_filename(__name__, 'htdocs'))]
        return []

    def get_templates_dirs(self):
        return [pkg_resources.resource_filename(__name__, 'templates')]


