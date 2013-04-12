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

r"""Milestone specifics for Bloodhound Search plugin."""
from bhsearch import BHSEARCH_CONFIG_SECTION
from bhsearch.api import (IIndexParticipant, BloodhoundSearchApi, IndexFields,
    ISearchParticipant)
from bhsearch.search_resources.base import BaseIndexer, BaseSearchParticipant
from bhsearch.search_resources.ticket_search import TicketIndexer
from bhsearch.utils import get_product
from trac.ticket import Milestone
from trac.config import ListOption, Option
from trac.core import implements
from trac.resource import IResourceChangeListener
from genshi.builder import tag

MILESTONE_TYPE = u"milestone"

class MilestoneFields(IndexFields):
    DUE = "due"
    COMPLETED = "completed"

class MilestoneIndexer(BaseIndexer):
    implements(IResourceChangeListener, IIndexParticipant)

    optional_fields = {
        'description': MilestoneFields.CONTENT,
        'due': MilestoneFields.DUE,
        'completed': MilestoneFields.COMPLETED,
    }

    # IResourceChangeListener methods
    def match_resource(self, resource):
        if isinstance(resource, Milestone):
            return True
        return False

    def resource_created(self, resource, context):
        # pylint: disable=unused-argument
        self._index_milestone(resource)

    def resource_changed(self, resource, old_values, context):
        # pylint: disable=unused-argument
        if "name" in old_values:
            self._rename_milestone(resource, old_values["name"])
        else:
            self._index_milestone(resource)

    def resource_deleted(self, resource, context):
        # pylint: disable=unused-argument
        try:
            search_api = BloodhoundSearchApi(self.env)
            search_api.delete_doc(
                get_product(self.env).prefix, MILESTONE_TYPE, resource.name)
        except Exception, e:
            if self.silence_on_error:
                self.log.error("Error occurs during milestone indexing. \
                    The error will not be propagated. Exception: %s", e)
            else:
                raise

    def _rename_milestone(self, milestone, old_name):
        try:
            doc = self.build_doc(milestone)
            search_api = BloodhoundSearchApi(self.env)
            with search_api.start_operation() as operation_context:
                search_api.change_doc_id(doc, old_name, operation_context)
                TicketIndexer(self.env).reindex_tickets(
                    search_api, operation_context, milestone=milestone.name)
        except Exception, e:
            if self.silence_on_error:
                self.log.error("Error occurs during renaming milestone from \
                 %s to %s. The error will not be propagated. Exception: %s",
                old_name, milestone.name, e)
            else:
                raise

    def _index_milestone(self, milestone):
        try:
            doc = self.build_doc(milestone)
            search_api = BloodhoundSearchApi(self.env)
            search_api.add_doc(doc)
        except Exception, e:
            if self.silence_on_error:
                self.log.error("Error occurs during wiki indexing. \
                    The error will not be propagated. Exception: %s", e)
            else:
                raise

    #IIndexParticipant members
    def build_doc(self, trac_doc):
        milestone = trac_doc
        #TODO: a lot of improvements must be added here.
        if milestone.is_completed:
            status = 'completed'
        else:
            status = 'open'
        doc = {
            IndexFields.ID: milestone.name,
            IndexFields.NAME: milestone.name,
            IndexFields.TYPE: MILESTONE_TYPE,
            IndexFields.STATUS: status,
            IndexFields.PRODUCT: get_product(self.env).prefix,
        }

        for field, index_field in self.optional_fields.iteritems():
            value = getattr(milestone, field, None)
            if value is not None:
                doc[index_field] = value

        return doc

    def get_entries_for_index(self):
        for milestone in Milestone.select(self.env, include_completed=True):
            yield self.build_doc(milestone)

class MilestoneSearchParticipant(BaseSearchParticipant):
    implements(ISearchParticipant)

    participant_type = MILESTONE_TYPE
    required_permission = 'MILESTONE_VIEW'

    default_facets = [
        IndexFields.PRODUCT,
    ]
    default_grid_fields = [
        MilestoneFields.ID, MilestoneFields.DUE, MilestoneFields.COMPLETED]
    prefix = MILESTONE_TYPE

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
        return "Milestone"

    def format_search_results(self, res):
        #TODO: add better milestone rendering

        name = res['hilited_name'] or res['name']
        return tag(u'[', res['product'], u'] Milestone:', name)
