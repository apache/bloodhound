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

r"""Ticket specifics for Bloodhound Search plugin."""
from bhsearch import BHSEARCH_CONFIG_SECTION
from bhsearch.api import (ISearchParticipant, BloodhoundSearchApi,
    IIndexParticipant, IndexFields)
from bhsearch.search_resources.base import BaseIndexer, BaseSearchParticipant
from bhsearch.utils import get_product
from genshi.builder import tag
from trac.ticket.api import TicketSystem
from trac.ticket import Ticket
from trac.config import ListOption, Option
from trac.core import implements
from trac.resource import IResourceChangeListener
from trac.ticket.model import Component

TICKET_TYPE = u"ticket"

class TicketFields(IndexFields):
    SUMMARY = "summary"
    MILESTONE = 'milestone'
    COMPONENT = 'component'
    KEYWORDS = "keywords"
    RESOLUTION = "resolution"
    CHANGES = 'changes'
    OWNER = 'owner'

class TicketIndexer(BaseIndexer):
    implements(IResourceChangeListener, IIndexParticipant)

    optional_fields = {
        'component': TicketFields.COMPONENT,
        'description': TicketFields.CONTENT,
        'keywords': TicketFields.KEYWORDS,
        'milestone': TicketFields.MILESTONE,
        'summary': TicketFields.SUMMARY,
        'status': TicketFields.STATUS,
        'resolution': TicketFields.RESOLUTION,
        'reporter': TicketFields.AUTHOR,
        'owner': TicketFields.OWNER,
    }

    def __init__(self):
        self.fields = TicketSystem(self.env).get_ticket_fields()
        self.text_area_fields = set(
            f['name'] for f in self.fields if f['type'] =='textarea')

    #IResourceChangeListener methods
    def match_resource(self, resource):
        if isinstance(resource, (Component, Ticket)):
            return True
        return False

    def resource_created(self, resource, context):
        # pylint: disable=unused-argument
        if isinstance(resource, Ticket):
            self._index_ticket(resource)

    def resource_changed(self, resource, old_values, context):
        # pylint: disable=unused-argument
        if isinstance(resource, Ticket):
            self._index_ticket(resource)
        elif isinstance(resource, Component):
            self._component_changed(resource, old_values)

    def resource_deleted(self, resource, context):
        # pylint: disable=unused-argument
        if isinstance(resource, Ticket):
            self._ticket_deleted(resource)

    def resource_version_deleted(self, resource, context):
        pass

    def _component_changed(self, component, old_values):
        if "name" in old_values:
            old_name = old_values["name"]
            try:
                search_api = BloodhoundSearchApi(self.env)
                with search_api.start_operation() as operation_context:
                    TicketIndexer(self.env).reindex_tickets(
                        search_api,
                        operation_context,
                        component=component.name)
            except Exception, e:
                if self.silence_on_error:
                    self.log.error("Error occurs during renaming Component \
                    from %s to %s. The error will not be propagated. \
                    Exception: %s",
                    old_name, component.name, e)
                else:
                    raise


    def _ticket_deleted(self, ticket):
        """Called when a ticket is deleted."""
        try:
            search_api = BloodhoundSearchApi(self.env)
            search_api.delete_doc(ticket.product, TICKET_TYPE, ticket.id)
        except Exception, e:
            if self.silence_on_error:
                self.log.error("Error occurs during deleting ticket. \
                    The error will not be propagated. Exception: %s", e)
            else:
                raise

    def reindex_tickets(self,
                        search_api,
                        operation_context,
                        **kwargs):
        for ticket in self._fetch_tickets(**kwargs):
            self._index_ticket(ticket, search_api, operation_context)

    def _fetch_tickets(self,  **kwargs):
        for ticket_id in self._fetch_ids(**kwargs):
            yield Ticket(self.env, ticket_id)

    def _fetch_ids(self, **kwargs):
        sql = "SELECT id FROM ticket"
        args = []
        conditions = []
        for key, value in kwargs.iteritems():
            args.append(value)
            conditions.append(key + "=%s")
        if conditions:
            sql = sql + " WHERE " + " AND ".join(conditions)
        for row in self.env.db_query(sql, args):
            yield int(row[0])

    def _index_ticket(self, ticket, search_api=None, operation_context=None):
        try:
            if not search_api:
                search_api = BloodhoundSearchApi(self.env)
            doc = self.build_doc(ticket)
            search_api.add_doc(doc, operation_context)
        except Exception, e:
            if self.silence_on_error:
                self.log.error("Error occurs during ticket indexing. \
                    The error will not be propagated. Exception: %s", e)
            else:
                raise

    #IIndexParticipant members
    def build_doc(self, trac_doc):
        ticket = trac_doc
        searchable_name = '#%(ticket.id)s %(ticket.id)s' %\
                          {'ticket.id': ticket.id}
        doc = {
            IndexFields.ID: str(ticket.id),
            IndexFields.NAME: searchable_name,
            '_stored_' + IndexFields.NAME: str(ticket.id),
            IndexFields.TYPE: TICKET_TYPE,
            IndexFields.TIME: ticket.time_changed,
            IndexFields.PRODUCT: get_product(self.env).prefix,
        }
        # TODO: Add support for moving tickets between products.


        for field, index_field in self.optional_fields.iteritems():
            if field in ticket.values:
                field_content = ticket.values[field]
                if field in self.text_area_fields:
                    field_content = self.wiki_formatter.format(field_content)
                doc[index_field] = field_content

        doc[TicketFields.CHANGES] = u'\n\n'.join(
            [self.wiki_formatter.format(x[4]) for x in ticket.get_changelog()
             if x[2] == u'comment'])
        return doc

    def get_entries_for_index(self):
        for ticket in self._fetch_tickets():
            yield self.build_doc(ticket)

class TicketSearchParticipant(BaseSearchParticipant):
    implements(ISearchParticipant)

    participant_type = TICKET_TYPE
    required_permission = 'TICKET_VIEW'

    default_facets = [
        IndexFields.PRODUCT,
        TicketFields.STATUS,
        TicketFields.MILESTONE,
        TicketFields.COMPONENT,
        ]
    default_grid_fields = [
        TicketFields.ID,
        TicketFields.SUMMARY,
        TicketFields.STATUS,
        TicketFields.MILESTONE,
        TicketFields.COMPONENT,
        ]
    prefix = TICKET_TYPE

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
        return "Ticket"

    def format_search_results(self, res):
        if not TicketFields.STATUS in res:
            stat = 'undefined_status'
            css_class = 'undefined_status'
        else:
            css_class = res[TicketFields.STATUS]
            if res[TicketFields.STATUS] == 'closed':
                resolution = ""
                if 'resolution' in res:
                    resolution = res['resolution']
                stat = '%s: %s' % (res['status'], resolution)
            else:
                stat = res[TicketFields.STATUS]

        id = res['hilited_id'] or res['id']
        id = tag.span('#', id, class_=css_class)
        summary = res['hilited_summary'] or res['summary']
        return tag('[', res['product'], '] ', id, ': ', summary, ' (%s)' % stat)

