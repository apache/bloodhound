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
from bhrelations.api import ResourceIdSerializer
from bhrelations.web_ui import RelationManagementModule
from bhrelations.tests.base import BaseRelationsTestCase

from multiproduct.ticket.web_ui import TicketModule
from trac.ticket import Ticket
from trac.util.datefmt import to_utimestamp
from trac.web import RequestDone


class RelationManagementModuleTestCase(BaseRelationsTestCase):
    def setUp(self):
        BaseRelationsTestCase.setUp(self)
        ticket_id = self._insert_ticket(self.env, "Foo")
        self.req.method = 'POST'
        self.req.args['id'] = ticket_id

    def test_can_process_empty_request(self):
        self.req.method = 'GET'
        data = self.process_request()

        self.assertSequenceEqual(data['relations'], [])
        self.assertEqual(len(data['reltypes']), 11)

    def test_handles_missing_ticket_id(self):
        self.req.args['add'] = 'add'

        data = self.process_request()

        self.assertIn("Invalid ticket", data["error"])

    def test_handles_invalid_ticket_id(self):
        self.req.args['add'] = True
        self.req.args['dest_tid'] = 'no such ticket'

        data = self.process_request()

        self.assertIn("Invalid ticket", data["error"])

    def test_handles_missing_relation_type(self):
        t2 = self._insert_ticket(self.env, "Bar")
        self.req.args['add'] = True
        self.req.args['dest_tid'] = str(t2)

        data = self.process_request()

        self.assertIn("Unknown relation type", data["error"])

    def test_handles_invalid_relation_type(self):
        t2 = self._insert_ticket(self.env, "Bar")
        self.req.args['add'] = True
        self.req.args['dest_tid'] = str(t2)
        self.req.args['reltype'] = 'no such relation'

        data = self.process_request()

        self.assertIn("Unknown relation type", data["error"])

    def test_shows_relation_that_was_just_added(self):
        t2 = self._insert_ticket(self.env, "Bar")
        self.req.args['add'] = True
        self.req.args['dest_tid'] = str(t2)
        self.req.args['reltype'] = 'dependson'

        data = self.process_request()

        self.assertEqual(len(data["relations"]), 1)

    def process_request(self):
        url, data, x = RelationManagementModule(self.env).process_request(
            self.req)
        return data


class ResolveTicketIntegrationTestCase(BaseRelationsTestCase):
    def setUp(self):
        BaseRelationsTestCase.setUp(self)

        self.mock_request()
        self.configure()

        self.req.redirect = self.redirect
        self.redirect_url = None
        self.redirect_permanent = None

    def test_creates_duplicate_relation_from_duplicate_id(self):
        t1 = self._insert_and_load_ticket("Foo")
        t2 = self._insert_and_load_ticket("Bar")

        self.assertRaises(RequestDone,
                          self.resolve_as_duplicate,
                          t2, self.get_id(t1))
        relations = self.relations_system.get_relations(t2)
        self.assertEqual(len(relations), 1)
        relation = relations[0]
        self.assertEqual(relation['destination_id'], self.get_id(t1))
        self.assertEqual(relation['type'], 'duplicateof')

    def test_prefills_duplicate_id_if_relation_exists(self):
        t1 = self._insert_and_load_ticket("Foo")
        t2 = self._insert_and_load_ticket("Bar")
        self.relations_system.add(t2, t1, 'duplicateof')
        self.req.path_info = '/ticket/%d' % t2.id

        data = self.process_request()

        self.assertIn('ticket_duplicate_of', data)
        t1id = ResourceIdSerializer.get_resource_id_from_instance(self.env, t1)
        self.assertEqual(data['ticket_duplicate_of'], t1id)

    def test_can_set_duplicate_resolution_even_if_relation_exists(self):
        t1 = self._insert_and_load_ticket("Foo")
        t2 = self._insert_and_load_ticket("Bar")
        self.relations_system.add(t2, t1, 'duplicateof')

        self.assertRaises(RequestDone,
                          self.resolve_as_duplicate,
                          t2, self.get_id(t1))
        t2 = Ticket(self.env, t2.id)
        self.assertEqual(t2['status'], 'closed')
        self.assertEqual(t2['resolution'], 'duplicate')

    def test_post_process_request_does_not_break_ticket(self):
        t1 = self._insert_and_load_ticket("Foo")
        self.req.path_info = '/ticket/%d' % t1.id
        self.process_request()

    def test_post_process_request_does_not_break_newticket(self):
        self.req.path_info = '/newticket'
        self.process_request()

    def test_post_process_request_can_handle_none_data(self):
        self.req.path_info = '/source'
        RelationManagementModule(self.env).post_process_request(
            self.req, '', None, '')

    def resolve_as_duplicate(self, ticket, duplicate_id):
        self.req.method = 'POST'
        self.req.path_info = '/ticket/%d' % ticket.id
        self.req.args['id'] = ticket.id
        self.req.args['action'] = 'resolve'
        self.req.args['action_resolve_resolve_resolution'] = 'duplicate'
        self.req.args['duplicate_id'] = duplicate_id
        self.req.args['view_time'] = str(to_utimestamp(ticket['changetime']))
        self.req.args['submit'] = True

        return self.process_request()

    def process_request(self):
        ticket_module = TicketModule(self.env)

        ticket_module.match_request(self.req)
        template, data, content_type = ticket_module.process_request(self.req)
        template, data, content_type = \
            RelationManagementModule(self.env).post_process_request(
                self.req, template, data, content_type)
        return data

    def mock_request(self):
        self.req.method = 'GET'
        self.req.get_header = lambda x: None
        self.req.authname = 'x'
        self.req.session = {}
        self.req.chrome = {'warnings': []}
        self.req.form_token = ''

    def configure(self):
        config = self.env.config
        config['ticket-workflow'].set('resolve', 'new -> closed')
        config['ticket-workflow'].set('resolve.operations', 'set_resolution')
        config['ticket-workflow'].set('resolve.permissions', 'TICKET_MODIFY')
        with self.env.db_transaction as db:
            db("INSERT INTO enum VALUES "
               "('resolution', 'duplicate', 'duplicate')")

    def redirect(self, url, permanent=False):
        self.redirect_url = url
        self.redirect_permanent = permanent
        raise RequestDone

    def get_id(self, ticket):
        return ResourceIdSerializer.get_resource_id_from_instance(self.env,
                                                                  ticket)


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(RelationManagementModuleTestCase, 'test'))
    return test_suite

if __name__ == '__main__':
    unittest.main()
