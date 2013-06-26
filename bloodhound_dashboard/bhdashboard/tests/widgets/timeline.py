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
import unittest
from bhdashboard.widgets.timeline import TicketFieldTimelineFilter
from trac.test import EnvironmentStub, Mock
from trac.ticket import Ticket


class TicketFieldTimelineFilterTests(unittest.TestCase):
    def setUp(self):
        self.env = EnvironmentStub()
        t1 = self._insert_and_load_ticket("foo")
        self.filter = TicketFieldTimelineFilter(self.env)
        self.context = context = Mock(resource=t1.resource)

    def tearDown(self):
        self.env.reset_db()

    def test_returns_none_for_invalid_ticket_id(self):
        event = ['ticket', None, None, ['88']]

        result = self.filter.filter_event(self.context, None, event, None)
        self.assertIsNone(result)

    def test_long_resource_id(self):
        """Test resource with long id (#547)"""
        resource = self.context.resource
        resource.id = long(resource.id)
        event = ['ticket', None, None, [resource]]

        result = self.filter.filter_event(self.context, None, event, None)
        self.assertEqual(result, event)

    def _insert_and_load_ticket(self, summary, **kw):
        ticket = Ticket(self.env)
        ticket["summary"] = summary
        for k, v in kw.items():
            ticket[k] = v
        return Ticket(self.env, ticket.insert())
