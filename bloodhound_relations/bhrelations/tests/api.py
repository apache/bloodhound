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
from _sqlite3 import OperationalError, IntegrityError
from bhrelations.api import EnvironmentSetup, RelationsSystem, CycleValidationError, ParentValidationError, TicketRelationsSpecifics
from trac.ticket.model import Ticket
from trac.test import EnvironmentStub, Mock
from trac.core import TracError
from trac.util.datefmt import utc
import unittest

try:
    from babel import Locale
    locale_en = Locale.parse('en_US')
except ImportError:
    locale_en = None

class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.env = EnvironmentStub(
            default_data=True,
            enable=['trac.*', 'bhrelations.*']
        )
        config_name = RelationsSystem.RELATIONS_CONFIG_NAME
        self.env.config.set(config_name, 'dependency', 'dependson,dependent')
        self.env.config.set(config_name, 'dependency.validator', 'no_cycle')
        self.env.config.set(config_name, 'parent_children','parent,children')
        self.env.config.set(config_name, 'parent_children.validator',
                                                            'parent_child')
        self.env.config.set(config_name, 'children.blocks', 'true')
        self.env.config.set(config_name, 'children.label', 'Overridden')
        self.env.config.set(config_name, 'parent.copy_fields',
                                                            'summary, foo')
        self.env.config.set(config_name, 'oneway', 'refersto')
        self.req = Mock(href=self.env.href, authname='anonymous', tz=utc,
                        args=dict(action='dummy'),
                        locale=locale_en, lc_time=locale_en)
        self.relations_system = RelationsSystem(self.env)
        self._upgrade_env()

    def tearDown(self):
        # shutil.rmtree(self.env.path)
        self.env.reset_db()

    def _upgrade_env(self):
        environment_setup = EnvironmentSetup(self.env)
        try:
            environment_setup.upgrade_environment(self.env.db_transaction)
        except OperationalError:
            # table remains but database version is deleted
            pass

    def _insert_ticket(self, summary, **kw):
        """Helper for inserting a ticket into the database"""
        ticket = Ticket(self.env)
        for k,v in kw.items():
            ticket[k] = v
        return ticket.insert()

    def _insert_and_load_ticket(self, summary, **kw):
        return Ticket(self.env, self._insert_ticket(summary, **kw))

    def test_can_add_two_ways_relations(self):
        #arrange
        ticket = self._insert_and_load_ticket("A1")
        dependent = self._insert_and_load_ticket("A2")
        #act
        relations_system = self.relations_system
        self._debug_select()
        relations_system.add(
            ticket, dependent, "dependent")
        #assert
        relations = relations_system.get_relations(ticket)
        self.assertEqual("dependent", relations[0]["type"])
        self.assertEqual(unicode(dependent.id), relations[0]["destination"].id)

        relations = relations_system.get_relations(dependent)
        self.assertEqual("dependson", relations[0]["type"])
        self.assertEqual(unicode(ticket.id), relations[0]["destination"].id)

    def test_can_add_single_way_relations(self):
        #arrange
        ticket = self._insert_and_load_ticket("A1")
        referred = self._insert_and_load_ticket("A2")
        #act
        relations_system = self.relations_system
        relations_system.add(ticket, referred, "refersto")
        #assert
        relations = relations_system.get_relations(ticket)
        self.assertEqual("refersto", relations[0]["type"])
        self.assertEqual(unicode(referred.id), relations[0]["destination"].id)

        relations = relations_system.get_relations(referred)
        self.assertEqual(0, len(relations))

    def test_can_add_multiple_relations(self):
        #arrange
        ticket = self._insert_and_load_ticket("A1")
        dependent1 = self._insert_and_load_ticket("A2")
        dependent2 = self._insert_and_load_ticket("A3")
        #act
        relations_system = self.relations_system
        relations_system.add(
            ticket, dependent1, "dependent")
        relations_system.add(
            ticket, dependent2, "dependent")
        #assert
        relations = relations_system.get_relations(ticket)
        self.assertEqual(2, len(relations))

    def test_will_not_create_more_than_one_identical_relations(self):
        #arrange
        ticket = self._insert_and_load_ticket("A1")
        dependent1 = self._insert_and_load_ticket("A2")
        #act
        relations_system = self.relations_system
        relations_system.add(
            ticket, dependent1, "dependent")
        self.assertRaisesRegexp(
            TracError,
            "already exists",
            relations_system.add,
            ticket, dependent1, "dependent")

    def test_will_not_create_more_than_one_identical_relations_db_level(self):
        sql = """INSERT INTO bloodhound_relations (source, destination, type)
                    VALUES (%s, %s, %s)"""
        with self.env.db_transaction as db:
            db(sql, ["1", "2", "dependson"])
            self.assertRaises(
                IntegrityError, db, sql, ["1", "2", "dependson"])

    def test_can_add_one_way_relations(self):
        #arrange
        ticket = self._insert_and_load_ticket("A1")
        referred_ticket = self._insert_and_load_ticket("A2")
        #act
        relations_system = self.relations_system
        relations_system.add(
            ticket, referred_ticket, "refersto")
        #assert
        relations = relations_system.get_relations(ticket)
        self.assertEqual("refersto", relations[0]["type"])
        self.assertEqual(unicode(referred_ticket.id),
                         relations[0]["destination"].id)

        relations = relations_system.get_relations(referred_ticket)
        self.assertEqual(0, len(relations))

    def test_can_delete_two_ways_relation(self):
        #arrange
        ticket = self._insert_and_load_ticket("A1")
        dependent_ticket = self._insert_and_load_ticket("A2")
        relations_system = self.relations_system
        relations_system.add(
            ticket, dependent_ticket, "dependson")
        relations = relations_system.get_relations(ticket)
        self.assertEqual(1, len(relations))
        #act
        relation_to_delete = relations[0]
        relations_system.delete(relation_to_delete["relation_id"])
        #assert
        relations = relations_system.get_relations(ticket)
        self.assertEqual(0, len(relations))

    def test_can_delete_single_way_relation(self):
        #arrange
        ticket = self._insert_and_load_ticket("A1")
        referred = self._insert_and_load_ticket("A2")
        #act
        relations_system = self.relations_system
        relations_system.add(ticket, referred, "refersto")


        ticket = self._insert_and_load_ticket("A1")
        dependent_ticket = self._insert_and_load_ticket("A2")
        relations_system = self.relations_system
        relations_system.add(
            ticket, dependent_ticket, "dependson")
        relations = relations_system.get_relations(ticket)

        self.assertEqual(1, len(relations))
        reverted_relations = relations_system.get_relations(dependent_ticket)
        self.assertEqual(1, len(reverted_relations))
        #act
        # self._debug_select()
        relation_to_delete = relations[0]
        relations_system.delete(relation_to_delete["relation_id"])
        #assert
        relations = relations_system.get_relations(ticket)
        self.assertEqual(0, len(relations))
        reverted_relations = relations_system.get_relations(dependent_ticket)
        self.assertEqual(0, len(reverted_relations))

    def test_can_not_add_cycled_immediate_relations(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        #act
        relations_system = self.relations_system
        relations_system.add(ticket1, ticket2, "dependson")

        try:
            relations_system.add(ticket2, ticket1, "dependson")
            self.assertFalse(True, "Should throw an exception")
        except CycleValidationError, ex:
            self.assertEqual(":ticket:1", ex.failed_ids[0])


    def test_can_add_more_dependsons(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        ticket3 = self._insert_and_load_ticket("A3")
        #act
        relations_system = self.relations_system
        relations_system.add(ticket1, ticket2, "dependson")
        relations_system.add(ticket1, ticket3, "dependson")

    def test_can_not_add_cycled_in_different_direction(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        #act
        relations_system = self.relations_system
        relations_system.add(ticket1, ticket2, "dependson")
        self.assertRaises(
            CycleValidationError,
            relations_system.add,
            ticket1,
            ticket2,
            "dependent")

    def test_can_not_add_cycled_relations(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        ticket3 = self._insert_and_load_ticket("A3")
        #act
        relations_system = self.relations_system
        relations_system.add(ticket1, ticket2, "dependson")
        relations_system.add(ticket2, ticket3, "dependson")
        self.assertRaisesRegexp(
            CycleValidationError,
            "Cycle in Dependson: #1 -> #2 -> #3",
            relations_system.add,
            ticket3,
            ticket1,
            "dependson")

    def test_can_not_add_more_than_one_parents(self):
        #arrange
        child = self._insert_and_load_ticket("A1")
        parent1 = self._insert_and_load_ticket("A2")
        parent2 = self._insert_and_load_ticket("A3")
        #act
        relations_system = self.relations_system
        relations_system.add(child, parent1, "parent")
        self.assertRaises(
            ParentValidationError,
            relations_system.add,
            child,
            parent2,
            "parent")

    def test_can_not_add_more_than_one_parents_via_children(self):
        #arrange
        child = self._insert_and_load_ticket("A1")
        parent1 = self._insert_and_load_ticket("A2")
        parent2 = self._insert_and_load_ticket("A3")
        #act
        relations_system = self.relations_system
        relations_system.add(parent1, child, "children")
        self.assertRaises(
            ParentValidationError,
            relations_system.add,
            parent2,
            child,
            "children")

    def test_ticket_can_be_resolved(self):
        #arrange
        child = self._insert_and_load_ticket("A1")
        parent1 = self._insert_and_load_ticket("A2")
        parent2 = self._insert_and_load_ticket("A3")
        #act
        relations_system = self.relations_system
        relations_system.add(parent1, child, "children")
        self.assertRaises(
            ParentValidationError,
            relations_system.add,
            parent2,
            child,
            "children")

    def test_blocked_ticket_cannot_be_resolved(self):
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        self.relations_system.add(ticket1, ticket2, "dependent")

        self.req.args=dict(action='resolve')
        ticket_relations = TicketRelationsSpecifics(self.env)
        warnings = ticket_relations.validate_ticket(self.req, ticket1)
        self.assertEqual(1, len(list(warnings)))

    #todo: add tests that relation were deleted when ticket was deleted

    #todo: add multi-product test
    def _debug_select(self):
        """
        used for debug purposes
        """
        print " source, destination, type"
        sql = "SELECT source, destination, type FROM bloodhound_relations"
        with self.env.db_query as db:
            # for row in db(sql, ("source", "destination", "type")):
            for row in db(sql):
                print row
