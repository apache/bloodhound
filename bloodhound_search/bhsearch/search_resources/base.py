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

r"""Base classes for Bloodhound Search plugin."""
import re

from bhsearch.api import ISearchWikiSyntaxFormatter
from trac.core import Component, implements
from trac.config import BoolOption, ExtensionOption

class BaseIndexer(Component):
    """
    This is base class for Bloodhound Search indexers of specific resource
    """
    silence_on_error = BoolOption('bhsearch', 'silence_on_error', "True",
        """If true, do not throw an exception during indexing a resource""")

    wiki_formatter = ExtensionOption('bhsearch', 'wiki_syntax_formatter',
        ISearchWikiSyntaxFormatter, 'SimpleSearchWikiSyntaxFormatter',
        'Name of the component implementing wiki syntax to text formatter \
        interface: ISearchWikiSyntaxFormatter.')


class BaseSearchParticipant(Component):
    default_view = None
    default_grid_fields = None
    default_facets = None
    participant_type = None
    required_permission = None

    def get_default_facets(self):
        return self.default_facets

    def get_default_view(self):
        return self.default_view

    def get_default_view_fields(self, view):
        if view == "grid":
            return self.default_grid_fields
        return None

    def is_allowed(self, req=None):
        return (not req or self.required_permission in req.perm)

    def get_participant_type(self):
        return self.participant_type

    def get_required_permission(self):
        return self.required_permission

class SimpleSearchWikiSyntaxFormatter(Component):
    """
    This class provide very naive formatting of wiki syntax to text
    appropriate for indexing and search result presentation.
    A lot of things can be improved here.
    """
    implements(ISearchWikiSyntaxFormatter)

    STRIP_CHARS = re.compile(r'([=#\'\"\*/])')
    REPLACE_CHARS = re.compile(r'([=#\[\]\{\}|])')

    WHITE_SPACE_RE = re.compile(r'([\s]+)')
    def format(self, wiki_content):
        if not wiki_content:
            return wiki_content
        intermediate = self.STRIP_CHARS.sub("", wiki_content)
        intermediate = self.REPLACE_CHARS.sub(" ", intermediate)
        result = self.WHITE_SPACE_RE.sub(" ", intermediate)
        return result.strip()


