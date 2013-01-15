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
from bhsearch.api import ISearchParticipant, BloodhoundSearchApi, IIndexParticipant, IndexFields
from genshi.builder import tag
from trac.core import *
from trac.ticket.api import ITicketChangeListener
from trac.ticket import Ticket
from trac.ticket.query import Query
from trac.config import Option

TICKET_TYPE = "ticket"
TICKET_STATUS = "status"

class TicketIndexer(Component):
    implements(ITicketChangeListener, IIndexParticipant)
    silence_on_error = Option('bhsearch', 'silence_on_error', "True",
        """If true, do not throw an exception during indexing a resource""")

    #ITicketChangeListener methods
    def ticket_created(self, ticket):
        """Index a recently created ticket."""
        self._index_ticket(ticket)

    def ticket_changed(self, ticket, comment, author, old_values):
        """Reindex a recently modified ticket."""
        self._index_ticket(ticket)

    def ticket_deleted(self, ticket):
        """Called when a ticket is deleted."""
        try:
            search_api = BloodhoundSearchApi(self.env)
            search_api.delete_doc(TICKET_TYPE, ticket.id)
        except Exception, e:
            if self.silence_on_error.lower() == "true":
                self.log.error("Error occurs during ticket indexing. \
                    The error will not be propagated. Exception: %s", e)
            else:
                raise

    def _index_ticket(
            self,
            ticket,
            raise_exception = False,
            ):
        try:
            search_api = BloodhoundSearchApi(self.env)
            doc = self.build_doc(ticket)
            search_api.add_doc(doc)
        except Exception, e:
            if (not raise_exception) and self.silence_on_error.lower() == "true":
                self.log.error("Error occurs during ticket indexing. \
                    The error will not be propagated. Exception: %s", e)
            else:
                raise

    #IIndexParticipant members
    def build_doc(self, trac_doc):
        ticket = trac_doc
        doc = {
            IndexFields.ID: unicode(ticket.id),
            IndexFields.TYPE: TICKET_TYPE,
            IndexFields.TIME: ticket.time_changed,
            }
        fields = [('component',),
                  ('description',IndexFields.CONTENT),
                  ('keywords',),
                  ('milestone',),
                  ('summary',),
                  ('status',),
                  ('resolution',),
                  ('reporter',IndexFields.AUTHOR),
        ]
        for f in fields:
          if f[0] in ticket.values:
              if len(f) == 1:
                  doc[f[0]] = ticket.values[f[0]]
              elif len(f) == 2:
                  doc[f[1]] = ticket.values[f[0]]
        doc['changes'] = u'\n\n'.join([x[4] for x in ticket.get_changelog()
          if x[2] == u'comment'])
        return doc

    def get_entries_for_index(self):
        #is there any better way to get all tickets?
        query_records = self._load_ticket_ids()
        for record in query_records:
            ticket = Ticket(self.env, record["id"])
            yield self.build_doc(ticket)

    def _load_ticket_ids(self):
        query = Query(self.env, cols=['id'], order='id')
        return query.execute()


class TicketSearchParticipant(Component):
    implements(ISearchParticipant)

    #ISearchParticipant members
    def get_search_filters(self, req=None):
        if not req or 'TICKET_VIEW' in req.perm:
            return TICKET_TYPE

    def get_title(self):
        return "Ticket"

    def format_search_results(self, res):
        if not TICKET_STATUS in res:
          stat = 'undefined_status'
          class_ = 'undefined_status'
        else:
            class_= res[TICKET_STATUS]
            if res[TICKET_STATUS] == 'closed':
                resolution = ""
                if 'resolution' in res:
                    resolution = res['resolution']
                stat = '%s: %s' % (res['status'], resolution)
            else:
                stat = res[TICKET_STATUS]

        id = tag(tag.span('#'+res['id'], class_=class_))
        return id + ': %s (%s)' % (res['summary'], stat)

