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
from bhsearch.api import ISearchParticipant, BloodhoundSearchApi
from genshi.builder import tag
from trac.core import *
from trac.ticket.api import ITicketChangeListener, TicketSystem
from trac.ticket import Ticket
from trac.ticket.query import Query
from trac.config import Option
from trac.web.chrome import add_warning
from trac.util.datefmt import to_datetime

TICKET = "ticket"
TICKET_STATUS = 'status'

class TicketSearchParticipant(Component):
    implements(ITicketChangeListener, ISearchParticipant)
    silence_on_error = Option('bhsearch', 'silence_on_error', "True",
        """If true, do not throw an exception during indexing a resource""")

    def _index_ticket(self, ticket, search_api=None, raise_exception = False):
        """Internal method for actually indexing a ticket.
        This reduces duplicating code."""
        try:
            if not search_api:
                search_api = BloodhoundSearchApi(self.env)

            #This is very naive prototype implementation
            #TODO: a lot of improvements must be added here!!!
            contents = {
                'id': unicode(ticket.id),
                'time': ticket.time_changed,
                'type': TICKET,
                }
            fields = [('component',), ('description','content'), ('component',),
                      ('keywords',), ('milestone',), ('summary',),
                      ('status',), ('resolution',), ('reporter','author')]
            for f in fields:
              if f[0] in ticket.values:
                  if len(f) == 1:
                      contents[f[0]] = ticket.values[f[0]]
                  elif len(f) == 2:
                      contents[f[1]] = ticket.values[f[0]]
            contents['changes'] = u'\n\n'.join([x[4] for x in ticket.get_changelog()
              if x[2] == u'comment'])
            search_api.add_doc(contents)
        except Exception, e:
            if (not raise_exception) and self.silence_on_error.lower() == "true":
                #Is there any way to get request object to add warning?
    #            add_warning(req, _('Exception during ticket indexing: %s' % e))
                self.log.error("Error occurs during ticke indexing. \
                    The error will not be propagated. Exception: %s", e)
            else:
                raise


    #ITicketChangeListener methods
    def ticket_created(self, ticket):
        """Index a recently created ticket."""
        self._index_ticket(ticket)

    def ticket_changed(self, ticket, comment, author, old_values):
        """Reindex a recently modified ticket."""
        self._index_ticket(ticket)

    def ticket_deleted(self, ticket):
        """Called when a ticket is deleted."""
        s = BloodhoundSearchApi(self.env)
        s.delete_doc(u'ticket', unicode(ticket.id))

    # ISearchParticipant methods
    def get_search_filters(self, req=None):
        if not req or 'TICKET_VIEW' in req.perm:
            return ('ticket', 'Tickets')

    def build_search_index(self, backend):
        """
        :type backend: ISearchBackend
        """
        #TODO: some king of paging/batch size should be introduced in order to
        # avoid loading of all ticket ids in memory
        query_records = self.load_tickets_ids()
        for record in query_records:
            ticket_id = record["id"]
            ticket = Ticket(self.env, ticket_id)
            self._index_ticket(ticket, backend, raise_exception=True)

    def load_tickets_ids(self):
        #is there better way to get all tickets?
        query = Query(self.env, cols=['id'], order='id')
        return query.execute()

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

