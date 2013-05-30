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

from bhrelations.web_ui import RelationManagementModule
from bhrelations.tests.api import BaseApiApiTestCase


class RelationManagementModuleTestCase(BaseApiApiTestCase):
    def setUp(self):
        BaseApiApiTestCase.setUp(self)
        ticket_id = self._insert_ticket(self.env, "Foo")
        args=dict(action='add', id=ticket_id, dest_tid='', reltype='', comment='')
        self.req.method = 'GET',
        self.req.args['id'] = ticket_id

    def test_can_process_empty_request(self):
        data = self.process_request()

        self.assertSequenceEqual(data['relations'], [])
        self.assertEqual(len(data['reltypes']), 11)

    def test_handles_missing_ticket_id(self):
        self.req.method = "POST"
        self.req.args['add'] = 'add'

        data = self.process_request()

        self.assertIn("Invalid ticket", data["error"])

    def test_handles_invalid_ticket_id(self):
        self.req.method = "POST"
        self.req.args['add'] = 'add'
        self.req.args['dest_tid'] = 'no such ticket'

        data = self.process_request()

        self.assertIn("Invalid ticket", data["error"])

    def test_handles_missing_relation_type(self):
        t2 = self._insert_ticket(self.env, "Bar")
        self.req.method = "POST"
        self.req.args['add'] = 'add'
        self.req.args['dest_tid'] = str(t2)

        data = self.process_request()

        self.assertIn("Unknown relation type", data["error"])

    def test_handles_invalid_relation_type(self):
        t2 = self._insert_ticket(self.env, "Bar")
        self.req.method = "POST"
        self.req.args['add'] = 'add'
        self.req.args['dest_tid'] = str(t2)
        self.req.args['reltype'] = 'no such relation'

        data = self.process_request()

        self.assertIn("Unknown relation type", data["error"])

    def test_shows_relation_that_was_just_added(self):
        t2 = self._insert_ticket(self.env, "Bar")
        self.req.method = "POST"
        self.req.args['add'] = 'add'
        self.req.args['dest_tid'] = str(t2)
        self.req.args['reltype'] = 'dependson'

        data = self.process_request()

        self.assertEqual(len(data["relations"]), 1)

    def process_request(self):
        url, data, x = RelationManagementModule(self.env).process_request(
            self.req)
        return data


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(RelationManagementModuleTestCase, 'test'))
    return test_suite

if __name__ == '__main__':
    unittest.main()
