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

r"""Wiki specifics for Bloodhound Search plugin."""
from bhsearch import BHSEARCH_CONFIG_SECTION
from bhsearch.api import (ISearchParticipant, BloodhoundSearchApi,
    IIndexParticipant, IndexFields)
from bhsearch.search_resources.base import BaseIndexer, BaseSearchParticipant
from bhsearch.utils import get_product
from trac.core import implements
from trac.config import ListOption, Option
from trac.wiki import IWikiChangeListener, WikiSystem, WikiPage
from genshi.builder import tag

WIKI_TYPE = u"wiki"


class WikiIndexer(BaseIndexer):
    implements(IWikiChangeListener, IIndexParticipant)

    #IWikiChangeListener methods
    def wiki_page_added(self, page):
        """Index a recently created ticket."""
        self._index_wiki(page)


    def wiki_page_changed(self, page, version, t, comment, author, ipnr):
        """Reindex a recently modified ticket."""
        # pylint: disable=too-many-arguments, unused-argument
        self._index_wiki(page)

    def wiki_page_deleted(self, page):
        """Called when a ticket is deleted."""
        try:
            search_api = BloodhoundSearchApi(self.env)
            search_api.delete_doc(
                get_product(self.env).prefix, WIKI_TYPE, page.name)
        except Exception, e:
            if self.silence_on_error.lower() == "true":
                self.log.error("Error occurs during wiki indexing. \
                    The error will not be propagated. Exception: %s", e)
            else:
                raise

    def wiki_page_version_deleted(self, page):
        """Called when a version of a page has been deleted."""
        self._index_wiki(page)

    def wiki_page_renamed(self, page, old_name):
        """Called when a page has been renamed."""
        try:
            doc = self.build_doc(page)
            search_api = BloodhoundSearchApi(self.env)
            search_api.change_doc_id(doc, old_name)
        except Exception, e:
            if self.silence_on_error:
                self.log.error("Error occurs during renaming wiki from %s \
                    to %s. The error will not be propagated. Exception: %s",
                old_name, page.name, e)
            else:
                raise

    def _index_wiki(self, page):
        try:
            doc = self.build_doc(page)
            search_api = BloodhoundSearchApi(self.env)
            search_api.add_doc(doc)
        except Exception, e:
            page_name = None
            if page is not None:
                page_name = page.name
            if self.silence_on_error:
                self.log.error("Error occurs during wiki indexing: %s. \
                    The error will not be propagated. Exception: %s",
                    page_name, e)
            else:
                raise

    #IIndexParticipant members
    def build_doc(self, trac_doc):
        page = trac_doc
        #This is very naive prototype implementation
        #TODO: a lot of improvements must be added here!!!
        searchable_name = page.name + ' ' + \
            WikiSystem(self.env).format_page_name(page.name, split=True)

        doc = {
            IndexFields.ID: page.name,
            IndexFields.NAME: searchable_name,
            '_stored_' + IndexFields.NAME: page.name,
            IndexFields.TYPE: WIKI_TYPE,
            IndexFields.TIME: page.time,
            IndexFields.AUTHOR: page.author,
            IndexFields.CONTENT: self.wiki_formatter.format(page.text),
            IndexFields.PRODUCT: get_product(self.env).prefix,
        }
        return doc

    def get_entries_for_index(self):
        page_names = WikiSystem(self.env).get_pages()
        for page_name in page_names:
            page = WikiPage(self.env, page_name)
            yield self.build_doc(page)

class WikiSearchParticipant(BaseSearchParticipant):
    implements(ISearchParticipant)

    participant_type = WIKI_TYPE
    required_permission = 'WIKI_VIEW'

    default_facets = [
        IndexFields.PRODUCT,
    ]
    default_grid_fields = [
        IndexFields.ID,
        IndexFields.TIME,
        IndexFields.AUTHOR,
        IndexFields.CONTENT,
    ]
    prefix = WIKI_TYPE

    default_facets = ListOption(
        BHSEARCH_CONFIG_SECTION,
        prefix + '_default_facets',
        default=",".join(default_facets),
        doc="""Default facets applied to search view of specific resource""")

    default_view = Option(
        BHSEARCH_CONFIG_SECTION,
        prefix + '_default_view',
        doc = """If true, show grid as default view for specific resource in
            Bloodhound Search results""")

    default_grid_fields = ListOption(
        BHSEARCH_CONFIG_SECTION,
        prefix + '_default_grid_fields',
        default = ",".join(default_grid_fields),
        doc="""Default fields for grid view for specific resource""")

    #ISearchParticipant members
    def get_title(self):
        return "Wiki"

    def format_search_results(self, res):
        title = res['hilited_name'] or res['name']
        return tag('[', res['product'], '] ', title)
