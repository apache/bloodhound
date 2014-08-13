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

from trac.ticket.model import Ticket
from trac.core import Component, implements, TracError
from bhsearch.search_resources.ticket_search import TicketIndexer
from bhsearch.search_resources.base import BaseIndexer

class TicketSearchModel(BaseIndexer):

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

    def get_entries_for_index(self):
        for ticket in self._fetch_tickets():
            yield TicketIndexer(self.env).build_doc(ticket)

