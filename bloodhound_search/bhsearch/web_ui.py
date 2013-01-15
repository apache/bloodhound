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

import pkg_resources
import re

from trac.core import *
from genshi.builder import tag
from trac.perm import IPermissionRequestor
from trac.search import shorten_result
from trac.config import OrderedExtensionsOption
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
    FILTER = "fl"
    TYPE = "type"
    NO_QUICK_JUMP = "noquickjump"
    PAGELEN = "pagelen"

    def __init__(self, req):
        self.req = req

        self.query = req.args.get(RequestParameters.QUERY)
        if self.query == None:
            self.query = ""

        #TODO: add quick jump functionality
        self.noquickjump = 1

        #TODO: add filters support
        self.filters = []

        #TODO: retrieve sort from query string
        self.sort = DEFAULT_SORT

        self.pagelen = int(req.args.get(
            RequestParameters.PAGELEN,
            DEFAULT_RESULTS_PER_PAGE))
        self.page = int(req.args.get(RequestParameters.PAGE, '1'))
        self.type = req.args.get(RequestParameters.TYPE, None)

        self.params = {
            self.NO_QUICK_JUMP: self.noquickjump,
        }
        if self.query:
            self.params[self.QUERY] = self.query
        if self.pagelen != DEFAULT_RESULTS_PER_PAGE:
            self.params[self.PAGELEN]=self.pagelen
        if self.page > 1:
            self.params[self.PAGE]=self.page
        if self.type:
            self.params[self.TYPE] = self.type

    def create_href(self, page = None, type=None, skip_type = False,
                    skip_page = False):
        params = dict(self.params)
        if page:
            params[self.PAGE] = page

        if skip_page and self.PAGE in params:
            del(params[self.PAGE])

        if type:
            params[self.TYPE] = type

        if skip_type and self.TYPE in params:
            #show all does not require type parameter
            del(params[self.TYPE])

        return self.req.href.bhsearch(**params)

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

        #TODO add quick jump support

        allowed_participants = self._get_allowed_participants(req)
        data = {
            'query': parameters.query,
            }

        #todo: filters check, tickets etc
        if not any((parameters.query, )):
            return self._return_data(req, data)

        query_filter = self._prepare_query_filter(
            parameters.type,
            parameters.filters,
            allowed_participants)

        #todo: add proper facets functionality
        facets = self._prepare_facets(req)

        querySystem = BloodhoundSearchApi(self.env)
        query_result = querySystem.query(
            parameters.query,
            pagenum = parameters.page,
            pagelen = parameters.pagelen,
            sort = parameters.sort,
            facets = facets,
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
        self._prepare_type_grouping(
            allowed_participants,
            parameters,
            data)

        #TODO:add proper facet links
        data['facets'] = query_result.facets
        data['page_href'] = parameters.create_href()
        return self._return_data(req, data)

    def _prepare_query_filter(self, type, filters, allowed_participants):
        query_filters = []

        if type in allowed_participants:
            query_filters.append((IndexFields.TYPE, type))
        else:
            self.log.debug("Unsupported type in web request: %s", type)

        #TODO: handle other filters
        return query_filters

    def _prepare_type_grouping(self, allowed_participants, parameters, data):
        active_type = parameters.type
        if active_type and active_type not in allowed_participants:
            raise TracError(_("Unsupported resource type: '%(name)s'",
                name=active_type))
        all_is_active = (active_type is None)
        grouping = [
            dict(
                label=_("All"),
                active=all_is_active,
                href=parameters.create_href(
                    skip_type=True,
                    skip_page=not all_is_active)
            )
        ]

        #we want to obtain the same order as specified in search_participants
        # option
        participant_with_type = dict((participant, type)
            for type, participant in allowed_participants.iteritems())
        for participant in self.search_participants:
            if participant in participant_with_type:
                type = participant_with_type[participant]
                is_active = (type == active_type)
                grouping.append(dict(
                    label=_(participant.get_title()),
                    active=is_active,
                    href=parameters.create_href(
                        type=type,
                        skip_page=not is_active
                    )
                ))
        data["types"] =  grouping
        data["active_type"] = active_type

    def _prepare_facets(self, req):
        facets = [IndexFields.TYPE]
        #TODO: add type specific default facets
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


