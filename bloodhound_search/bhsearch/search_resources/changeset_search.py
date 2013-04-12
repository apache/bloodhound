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

from bhsearch import BHSEARCH_CONFIG_SECTION
from trac.versioncontrol.api import IRepositoryChangeListener
from bhsearch.api import (IIndexParticipant, BloodhoundSearchApi, IndexFields,
                          ISearchParticipant)
from bhsearch.search_resources.base import BaseIndexer, BaseSearchParticipant
from genshi.builder import tag
from trac.config import ListOption, Option
from trac.core import implements
from trac.versioncontrol.api import RepositoryManager

CHANGESET_TYPE = u"changeset"


class ChangesetFields(IndexFields):
    MESSAGE = "message"
    REPOSITORY = "repository"
    REVISION = "revision"
    CHANGES = "changes"


class ChangesetIndexer(BaseIndexer):
    implements(IRepositoryChangeListener, IIndexParticipant)

    # IRepositoryChangeListener methods
    def changeset_added(self, repos, changeset):
        # pylint: disable=unused-argument
        self._index_changeset(changeset)

    def changeset_modified(self, repos, changeset, old_changeset):
        # pylint: disable=unused-argument
        self._index_changeset(changeset)

    def _index_changeset(self, changeset):
        try:
            doc = self.build_doc(changeset)
            search_api = BloodhoundSearchApi(self.env)
            search_api.add_doc(doc)
        except Exception, e:
            if self.silence_on_error:
                self.log.error("Error occurs during changeset indexing. \
                    The error will not be propagated. Exception: %s", e)
            else:
                raise

    #IIndexParticipant members
    def build_doc(self, trac_doc):
        changeset = trac_doc

        doc = {
            IndexFields.ID: u'%s/%s' % (changeset.rev,
                                        changeset.repos.reponame),
            IndexFields.TYPE: CHANGESET_TYPE,
            ChangesetFields.MESSAGE: changeset.message,
            IndexFields.AUTHOR: changeset.author,
            IndexFields.TIME: changeset.date,
            ChangesetFields.REPOSITORY: changeset.repos.reponame,
            ChangesetFields.REVISION: changeset.repos.short_rev(changeset.rev)
        }
        return doc

    def get_entries_for_index(self):
        repository_manager = RepositoryManager(self.env)
        for repository in repository_manager.get_real_repositories():
            rev = repository.oldest_rev
            stop = repository.youngest_rev
            while True:
                changeset = repository.get_changeset(rev)
                yield self.build_doc(changeset)
                if rev == stop:
                    break
                rev = repository.next_rev(rev)


class ChangesetSearchParticipant(BaseSearchParticipant):
    implements(ISearchParticipant)

    participant_type = CHANGESET_TYPE
    required_permission = 'CHANGESET_VIEW'

    default_facets = [
        IndexFields.PRODUCT,
        ChangesetFields.REPOSITORY,
        ChangesetFields.AUTHOR,
    ]
    default_grid_fields = [
        ChangesetFields.REPOSITORY,
        ChangesetFields.REVISION,
        ChangesetFields.AUTHOR,
        ChangesetFields.MESSAGE
    ]
    prefix = CHANGESET_TYPE

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
        default=",".join(default_grid_fields),
        doc="""Default fields for grid view for specific resource""")

    #ISearchParticipant members
    def get_title(self):
        return "Changeset"

    def format_search_results(self, res):
        message = res['hilited_message'] or res['message']
        return tag(u'Changeset [', res['revision'], u']: ', message)
