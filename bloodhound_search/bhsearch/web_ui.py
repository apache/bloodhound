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
from trac.util.presentation import Paginator
from trac.util.datefmt import format_datetime, user_time
from trac.web import IRequestHandler
from trac.util.translation import _
from trac.web.chrome import (INavigationContributor, ITemplateProvider,
                             add_link, add_stylesheet, add_warning,
                             web_context)
from bhsearch.api import BloodhoundSearchApi, ISearchParticipant, SCORE, ASC, DESC

SEARCH_PERMISSION = 'SEARCH_VIEW'

class BloodhoundSearchModule(Component):
    """Main search page"""

    implements(INavigationContributor, IPermissionRequestor, IRequestHandler,
               ITemplateProvider,
    #           IWikiSyntaxProvider #todo: implement later
    )

    search_participants = ExtensionPoint(ISearchParticipant)

    RESULTS_PER_PAGE = 10
    DEFAULT_SORT = [(SCORE, ASC), ("time", DESC)]


    # INavigationContributor methods
    def get_active_navigation_item(self, req):
        return 'bhsearch'

    def get_navigation_items(self, req):
        if SEARCH_PERMISSION in req.perm:
            yield ('mainnav', 'bhsearch',
                   tag.a(_('Bloodhound Search'), href=self.env.href.bhsearch()))

    # IPermissionRequestor methods
    def get_permission_actions(self):
        return [SEARCH_PERMISSION]

    # IRequestHandler methods

    def match_request(self, req):
        return re.match(r'/bhsearch?', req.path_info) is not None

    def process_request(self, req):
        req.perm.assert_permission(SEARCH_PERMISSION)

        query = req.args.get('q')
        if query == None:
            query = ""

        #TODO add quick jump support

        #TODO: refactor filters or replace with facets
        filters = []
#        available_filters = filter(None, [p.get_search_filters(req) for p
#            in self.search_participants])
#        filters = [f[0] for f in available_filters if req.args.has_key(f[0])]
#        if not filters:
#            filters = [f[0] for f in available_filters
#                       if f[0] not in self.default_disabled_filters and
#                       (len(f) < 3 or len(f) > 2 and f[2])]
#        data = {'filters': [{'name': f[0], 'label': f[1],
#                             'active': f[0] in filters}
#                            for f in available_filters],
#                'quickjump': None,
#                'results': []}

        data = {
      			'query': query,
      		}

        # Initial page request
        #todo: filters check, tickets etc
        if not any((query, )):
            return self._return_data(req, data)

        page = int(req.args.get('page', '1'))

        #todo: retrieve sort from query string
        sort = self.DEFAULT_SORT

        #todo: add proper facets functionality
#        facets = ("type", "status")
        facets = ("type",)


        querySystem = BloodhoundSearchApi(self.env)
        query_result = querySystem.query(
            query,
            pagenum = page,
            pagelen = self.RESULTS_PER_PAGE,
            sort = sort,
            facets = facets,
        )
        ui_docs = [self._process_doc(doc, req)
                   for doc in query_result.docs]


        results = Paginator(
            ui_docs,
            page - 1,
            self.RESULTS_PER_PAGE,
            query_result.hits,
        )

        results.shown_pages = self._prepare_shown_pages(
            filters,
            query,
            req,
            shown_pages = results.get_shown_pages(self.RESULTS_PER_PAGE))

        results.current_page = {'href': None, 'class': 'current',
                                'string': str(results.page + 1),
                                'title':None}

        if results.has_next_page:
            next_href = req.href.bhsearch(zip(filters, ['on'] * len(filters)),
                                        q=req.args.get('q'), page=page + 1,
                                        noquickjump=1)
            add_link(req, 'next', next_href, _('Next Page'))

        if results.has_previous_page:
            prev_href = req.href.bhsearch(zip(filters, ['on'] * len(filters)),
                                        q=req.args.get('q'), page=page - 1,
                                        noquickjump=1)
            add_link(req, 'prev', prev_href, _('Previous Page'))

        data['results'] = results

        #add proper facet links
        data['facets'] = query_result.facets

        data['page_href'] = req.href.bhsearch(
            zip(filters, ['on'] * len(filters)), q=req.args.get('q'),
            noquickjump=1)
        return self._return_data(req, data)

    def _return_data(self, req, data):
        add_stylesheet(req, 'common/css/search.css')
        return 'bhsearch.html', data, None

    def _process_doc(self, doc,req):
        titlers = dict([(x.get_search_filters(req)[0], x.format_search_results)
            for x in self.search_participants if x.get_search_filters(req)])

        #todo: introduce copy by predefined value
        ui_doc = dict(doc)

        ui_doc["href"] = req.href(doc['type'], doc['id'])
        #todo: perform content adaptation here
        if doc.has_key('content'):
            ui_doc['excerpt'] = shorten_result(doc['content'])
        if doc.has_key('time'):
            ui_doc['date'] = user_time(req, format_datetime, doc['time'])

        ui_doc['title'] = titlers[doc['type']](doc)
        return ui_doc

    def _prepare_shown_pages(self, filters, query, req, shown_pages):
        pagedata = []
        for shown_page in shown_pages:
            page_href = req.href.bhsearch([(f, 'on') for f in filters],
                q=query,
                page=shown_page, noquickjump=1)
            pagedata.append([page_href, None, str(shown_page),
                             'page ' + str(shown_page)])
        fields = ['href', 'class', 'string', 'title']
        result_shown_pages = [dict(zip(fields, p)) for p in pagedata]
        return result_shown_pages


    # ITemplateProvider methods
    def get_htdocs_dirs(self):
#        return [('bhsearch', pkg_resources.resource_filename(__name__, 'htdocs'))]
        return []

    def get_templates_dirs(self):
        return [pkg_resources.resource_filename(__name__, 'templates')]


