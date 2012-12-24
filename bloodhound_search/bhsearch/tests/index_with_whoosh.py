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
from datetime import datetime

import unittest
import tempfile
import shutil
from bhsearch.api import BloodhoundSearchApi
from bhsearch.tests.utils import BaseBloodhoundSearchTest
from bhsearch.ticket_search import TicketSearchParticipant

from bhsearch.whoosh_backend import WhooshBackend
from trac.test import EnvironmentStub
from trac.ticket.api import TicketSystem


class IndexWhooshTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        self.env = EnvironmentStub(enable=['bhsearch.*'])
        self.env.path = tempfile.mkdtemp('bhsearch-tempenv')
#        self.perm = PermissionSystem(self.env)
        self.whoosh_backend = WhooshBackend(self.env)
        self.whoosh_backend.recreate_index()
        self.search_api = BloodhoundSearchApi(self.env)
        self.ticket_participant = TicketSearchParticipant(self.env)
        self.ticket_system = TicketSystem(self.env)

    def tearDown(self):
        shutil.rmtree(self.env.path)
        self.env.reset_db()

    def test_can_index_ticket(self):
        ticket = self.create_dummy_ticket()
        ticket.id = "1"
        self.ticket_participant.ticket_created(ticket)

        results = self.search_api.query("*:*")
        self.print_result(results)
        self.assertEqual(1, results.hits)

    def test_that_ticket_indexed_when_inserted_in_db(self):
        ticket = self.create_dummy_ticket()
        ticket_id = ticket.insert()
        print "Created ticket #%s" % ticket_id

        results = self.search_api.query("*:*")
        self.print_result(results)
        self.assertEqual(1, results.hits)

    def test_can_reindex(self):
        self.insert_ticket("t1")
        self.insert_ticket("t2")
        self.insert_ticket("t3")
        self.whoosh_backend.recreate_index()
        #act
        self.search_api.rebuild_index()
        #assert
        results = self.search_api.query("*:*")
        self.print_result(results)
        self.assertEqual(3, results.hits)


def suite():
    return unittest.makeSuite(IndexWhooshTestCase, 'test')

if __name__ == '__main__':
    unittest.main()
