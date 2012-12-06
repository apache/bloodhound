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

"""Bloodhound Search user interface"""

import pkg_resources
import re

from trac.core import *
from genshi.builder import tag
from trac.perm import IPermissionRequestor
from trac.web import IRequestHandler
from trac.util.translation import _
from trac.web.chrome import (INavigationContributor, ITemplateProvider,
                             add_link, add_stylesheet, add_warning,
                             web_context)
from bhsearch.api import BloodhoundQuerySystem

SEARCH_PERMISSION = 'SEARCH_VIEW'

class BloodhoundSearchModule(Component):
    """Main search page"""

    implements(INavigationContributor, IPermissionRequestor, IRequestHandler,
               ITemplateProvider,
    #           IWikiSyntaxProvider #todo: implement later
    )

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

        data = {}
        if query:
            data["query"] = query

        #TODO: add implementation here
        querySystem = BloodhoundQuerySystem(self.env)
        result = querySystem.query(query)

        add_stylesheet(req, 'common/css/search.css')
        return 'bhsearch.html', data, None

    # ITemplateProvider methods
    def get_htdocs_dirs(self):
#        return [('bhsearch', pkg_resources.resource_filename(__name__, 'htdocs'))]
        return []

    def get_templates_dirs(self):
        return [pkg_resources.resource_filename(__name__, 'templates')]

