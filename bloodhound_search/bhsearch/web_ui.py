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
from bhsearch import BHSEARCH_CONFIG_SECTION
import re

from trac.core import Component, implements, TracError
from genshi.builder import tag
from trac.perm import IPermissionRequestor
from trac.search import shorten_result
from trac.config import OrderedExtensionsOption, ListOption, Option
from trac.util.presentation import Paginator
from trac.util.datefmt import format_datetime, user_time
from trac.web import IRequestHandler
from trac.util.translation import _
from trac.util.html import find_element
from trac.web.chrome import (INavigationContributor, ITemplateProvider,
                             add_link, add_stylesheet, web_context)
from bhsearch.api import (BloodhoundSearchApi, ISearchParticipant, SCORE, ASC,
                          DESC, IndexFields)
from trac.wiki.formatter import extract_link

SEARCH_PERMISSION = 'SEARCH_VIEW'
DEFAULT_RESULTS_PER_PAGE = 10

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
    VIEW = "view"
    SORT = "sort"

    def __init__(self, req):
        self.req = req

        self.original_query = req.args.getfirst(self.QUERY)
        if self.original_query is None:
            self.query = ""
        else:
            self.query = self.original_query.strip()

        self.no_quick_jump = int(req.args.getfirst(self.NO_QUICK_JUMP, '0'))

        self.view = req.args.getfirst(self.VIEW)
        self.filter_queries = req.args.getlist(self.FILTER_QUERY)
        self.filter_queries = self._remove_possible_duplications(
            self.filter_queries)

        sort_string = req.args.getfirst(self.SORT)
        self.sort = self._parse_sort(sort_string)

        self.pagelen = int(req.args.getfirst(
            RequestParameters.PAGELEN,
            DEFAULT_RESULTS_PER_PAGE))
        self.page = int(req.args.getfirst(self.PAGE, '1'))
        self.type = req.args.getfirst(self.TYPE)

        self.params = {
            RequestParameters.FILTER_QUERY: []
        }

        if self.original_query is not None:
            self.params[self.QUERY] = self.original_query
        if self.no_quick_jump > 0:
            self.params[self.NO_QUICK_JUMP] = self.no_quick_jump
        if self.view is not None:
            self.params[self.VIEW] = self.view
        if self.pagelen != DEFAULT_RESULTS_PER_PAGE:
            self.params[self.PAGELEN] = self.pagelen
        if self.page > 1:
            self.params[self.PAGE] = self.page
        if self.type:
            self.params[self.TYPE] = self.type
        if self.filter_queries:
            self.params[RequestParameters.FILTER_QUERY] = self.filter_queries
        if sort_string:
            self.params[RequestParameters.SORT] = sort_string

    def _parse_sort(self, sort_string):
        if not sort_string:
            return None
        sort_terms = sort_string.split(",")
        sort = []

        def parse_sort_order(sort_order):
            sort_order = sort_order.lower()
            if sort_order == ASC:
                return ASC
            elif sort_order == DESC:
                return DESC
            else:
                raise TracError(
                    "Invalid sort order %s in sort parameter %s" %
                    (sort_order, sort_string))

        for term in sort_terms:
            term = term.strip()
            if not term:
                continue
            term_parts = term.split()
            parts_count = len(term_parts)
            if parts_count == 1:
                sort.append((term_parts[0], ASC))
            elif parts_count == 2:
                sort.append((term_parts[0], parse_sort_order(term_parts[1])))
            else:
                raise TracError("Invalid sort term %s " % term)

        return sort if sort else None



    def _remove_possible_duplications(self, parameters_list):
        seen = set()
        return [parameter for parameter in parameters_list
                if parameter not in seen and not seen.add(parameter)]

    def create_href(
            self,
            page=None,
            type=None,
            skip_type=False,
            skip_page=False,
            additional_filter=None,
            force_filters=None,
            view=None,
            skip_view=False,
    ):
        params = copy.deepcopy(self.params)

        #noquickjump parameter should be always set to 1 for urls
        params[self.NO_QUICK_JUMP] = 1

        if skip_view:
            self._delete_if_exists(params, self.VIEW)
        elif view:
            params[self.VIEW] = view

        if skip_page:
            self._delete_if_exists(params, self.PAGE)
        elif page:
            params[self.PAGE] = page

        if skip_type:
            self._delete_if_exists(params, self.TYPE)
        elif type:
            params[self.TYPE] = type

        if additional_filter and\
           additional_filter not in params[self.FILTER_QUERY]:
            params[self.FILTER_QUERY].append(additional_filter)
        elif force_filters is not None:
            params[self.FILTER_QUERY] = force_filters

        return self.req.href.bhsearch(**params)

    def _delete_if_exists(self, params, name):
        if name in params:
            del params[name]

    def is_show_all_mode(self):
        return self.type is None


class BloodhoundSearchModule(Component):
    """Main search page"""
    DATA_HEADERS = "headers"
    DATA_ALL_VIEWS = "all_views"
    DATA_ACTIVE_VIEW = "active_view"
    DATA_VIEW = "view"
    DATA_VIEW_GRID = "grid"
    #bhsearch may support more pluggable views later
    VIEWS_SUPPORTED = {
        None: "Free text",
        DATA_VIEW_GRID: "Grid"
    }
    VIEWS_WITH_KNOWN_FIELDS = [DATA_VIEW_GRID]
    OBLIGATORY_FIELDS_TO_SELECT = [IndexFields.ID, IndexFields.TYPE]
    DEFAULT_SORT = [(SCORE, ASC), ("time", DESC)]

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

    prefix = "all"
    default_grid_fields = [
        IndexFields.ID,
        IndexFields.TYPE,
        IndexFields.TIME,
        IndexFields.AUTHOR,
        IndexFields.CONTENT,
    ]

    default_facets = ListOption(
        BHSEARCH_CONFIG_SECTION,
        prefix + '_default_facets',
        doc="""Default facets applied to search view of all resources""")

    default_view = Option(
        BHSEARCH_CONFIG_SECTION,
        prefix + '_default_view',
        doc="""If true, show grid as default view for specific resource in
            Bloodhound Search results""")

    default_grid_fields = ListOption(
        BHSEARCH_CONFIG_SECTION,
        prefix + '_default_grid_fields',
        default=",".join(default_grid_fields),
        doc="""Default fields for grid view for specific resource""")


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
        allowed_participants = self._get_allowed_participants(req)
        data = {
            'query': parameters.query,
        }
        self._prepare_allowed_types(allowed_participants, parameters, data)
        self._prepare_active_filter_queries(
            parameters,
            data,
        )

        #TBD: should search return results on empty query?
        #        if not any((
        #            query,
        #            parameters.type,
        #            parameters.filter_queries,
        #            )):
        #            return self._return_data(req, data)

        self._prepare_quick_jump(
            parameters,
            data)
        fields = self._prepare_fields_and_view(
            allowed_participants, parameters, data)

        query_filter = self._prepare_query_filter(
            parameters, allowed_participants)

        facets = self._prepare_facets(parameters, allowed_participants)

        sort = parameters.sort if parameters.sort else self.DEFAULT_SORT

        query_system = BloodhoundSearchApi(self.env)
        query_result = query_system.query(
            parameters.query,
            pagenum=parameters.page,
            pagelen=parameters.pagelen,
            sort=sort,
            fields=fields,
            facets=facets,
            filter=query_filter,
        )

        is_free_text_view = (self.DATA_VIEW not in data)
        ui_docs = [self._process_doc(
                        doc, req, allowed_participants, is_free_text_view)
                   for doc in query_result.docs]

        results = Paginator(
            ui_docs,
            parameters.page - 1,
            parameters.pagelen,
            query_result.hits)

        results.shown_pages = self._prepare_shown_pages(
            parameters,
            shown_pages=results.get_shown_pages(parameters.pagelen))

        results.current_page = {'href': None,
                                'class': 'current',
                                'string': str(results.page + 1),
                                'title': None}

        if results.has_next_page:
            next_href = parameters.create_href(page=parameters.page + 1)
            add_link(req, 'next', next_href, _('Next Page'))

        if results.has_previous_page:
            prev_href = parameters.create_href(page=parameters.page - 1)
            add_link(req, 'prev', prev_href, _('Previous Page'))

        data['results'] = results
        data['debug'] = query_result.debug

        self._prepare_result_facet_counts(
            parameters,
            query_result,
            data,
        )

        data['page_href'] = parameters.create_href()
        return self._return_data(req, data)


    def _prepare_fields_and_view(self, allowed_participants, parameters, data):
        self._add_views_selector(parameters, data)
        active_participant = self._get_active_participant(
            parameters, allowed_participants)
        view = self._get_view(parameters, active_participant)
        if view:
            data[self.DATA_VIEW] = view
        fields_to_select = None
        if view in self.VIEWS_WITH_KNOWN_FIELDS:
            if active_participant:
                fields_in_view = active_participant.get_default_view_fields(
                    view)
            elif view == self.DATA_VIEW_GRID:
                fields_in_view = self.default_grid_fields
            else:
                raise TracError("Unsupported view: %s" % view)
            data[self.DATA_HEADERS] = [self._create_headers_item(field)
                                        for field in fields_in_view]
            fields_to_select = self._optionally_add_obligatory_fields(
                fields_in_view)
        return fields_to_select

    def _add_views_selector(self, parameters, data):
        active_view = parameters.view
        all_views = []
        for view, label in self.VIEWS_SUPPORTED.iteritems():
            all_views.append(dict(
                label=_(label),
                href=parameters.create_href(
                    view=view, skip_view=(view is None)),
                is_active = (view == active_view)
            ))
        data[self.DATA_ALL_VIEWS] = all_views
        if parameters.view:
            data[self.DATA_ACTIVE_VIEW] = parameters.view

    def _optionally_add_obligatory_fields(self, fields_in_view):
        fields_to_select = list(fields_in_view)
        for obligatory_field in self.OBLIGATORY_FIELDS_TO_SELECT:
            if obligatory_field is not fields_to_select:
                fields_to_select.append(obligatory_field)
        return fields_to_select

    def _create_headers_item(self, field):
        return dict(
            name=field,
            href="",
            #TODO:add translated column label. Now it is really temporary
            #workaround
            label=field,
            sort=None,
        )

    def _get_view(self, parameters, active_participant):
        view = parameters.view
        if view is None:
            if active_participant is not None:
                view = active_participant.get_default_view()
            else:
                view = self.default_view
        if view is not None:
            view =  view.strip().lower()
        return view


    def _get_active_participant(self, parameters, allowed_participants):
        active_type = parameters.type
        if active_type is not None and \
           active_type in allowed_participants:
            return allowed_participants[active_type]
        else:
            return None


    def _prepare_quick_jump(self,
                            parameters,
                            data):
        if not parameters.query:
            return
        check_result = self._check_quickjump(
            parameters.req,
            parameters.query)
        if check_result:
            data["quickjump"] = check_result

    #the method below is "copy/paste" from trac search/web_ui.py
    def _check_quickjump(self, req, kwd):
        """Look for search shortcuts"""
        noquickjump = int(req.args.get('noquickjump', '0'))
        # Source quickjump   FIXME: delegate to ISearchSource.search_quickjump
        quickjump_href = None
        if kwd[0] == '/':
            quickjump_href = req.href.browser(kwd)
            name = kwd
            description = _('Browse repository path %(path)s', path=kwd)
        else:
            context = web_context(req, 'search')
            link = find_element(extract_link(self.env, context, kwd), 'href')
            if link is not None:
                quickjump_href = link.attrib.get('href')
                name = link.children
                description = link.attrib.get('title', '')
        if quickjump_href:
            # Only automatically redirect to local quickjump links
            if not quickjump_href.startswith(req.base_path or '/'):
                noquickjump = True
            if noquickjump:
                return {'href': quickjump_href, 'name': tag.EM(name),
                        'description': description}
            else:
                req.redirect(quickjump_href)


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
                    active=(type == active_type),
                    href=parameters.create_href(
                        type=type,
                        skip_page=True,
                        force_filters=[],
                    ),
                ))
        data["types"] = allowed_types
        data["active_type"] = active_type


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
                    if field == IndexFields.TYPE:
                        href = parameters.create_href(
                            skip_page=True,
                            force_filters=[],
                            type=field_value)
                    else:
                        href = parameters.create_href(
                            skip_page=True,
                            additional_filter=self._create_term_expression(
                                field,
                                field_value)
                        )
                    per_field_dict[field_value] = dict(
                        count=count,
                        href=href
                    )
                facet_counts[_(field)] = per_field_dict

        data['facet_counts'] = facet_counts

    def _create_term_expression(self, field, field_value):
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
                self._create_term_expression(IndexFields.TYPE, type))
        else:
            self.log.debug("Unsupported type in web request: %s", type)
        return query_filters

    def _prepare_facets(self, parameters, allowed_participants):
        #TODO: add possibility of specifying facets in query parameters
        if parameters.is_show_all_mode():
            facets = [IndexFields.TYPE]
            facets.extend(self.default_facets)
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

    def _process_doc(self, doc, req, allowed_participants, is_free_text_view):
        ui_doc = dict(doc)
        ui_doc["href"] = req.href(doc['type'], doc['id'])
        #todo: perform content adaptation here
        if doc.has_key('content'):
#            ui_doc['excerpt'] = shorten_result(doc['content'])
            ui_doc['content'] = shorten_result(doc['content'])
        if doc.has_key('time'):
            ui_doc['date'] = user_time(req, format_datetime, doc['time'])

        if is_free_text_view:
            ui_doc['title'] = allowed_participants[
                              doc['type']].format_search_results(doc)
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


