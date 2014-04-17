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
from datetime import datetime

from trac.core import TracError
from trac.ticket.model import Ticket
from trac.util.datefmt import utc

from multiproduct.env import ProductEnvironment

from bhrelations.api import TicketRelationsSpecifics
from bhrelations.tests.mocks import TestRelationChangingListener
from bhrelations.validation import ValidationError
from bhrelations.tests.base import BaseRelationsTestCase, BLOCKED_BY, \
                                   BLOCKS, CHILD, DEPENDENCY_OF, DEPENDS_ON, \
                                   DUPLICATE_OF, MULTIPRODUCT_REL, PARENT, \
                                   REFERS_TO


class ApiTestCase(BaseRelationsTestCase):
    def test_can_add_two_ways_relations(self):
        #arrange
        ticket = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        #act
        self.add_relation(ticket, DEPENDENCY_OF, ticket2)
        #assert
        relations = self.get_relations(ticket)
        self.assertEqual(DEPENDENCY_OF, relations[0]["type"])
        self.assertEqual(unicode(ticket2.id), relations[0]["destination"].id)

        relations = self.get_relations(ticket2)
        self.assertEqual(DEPENDS_ON, relations[0]["type"])
        self.assertEqual(unicode(ticket.id), relations[0]["destination"].id)

    def test_can_add_single_way_relations(self):
        #arrange
        ticket = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        #act
        self.add_relation(ticket, REFERS_TO, ticket2)
        #assert
        relations = self.get_relations(ticket)
        self.assertEqual(1, len(relations))
        self.assertEqual(REFERS_TO, relations[0]["type"])
        self.assertEqual(unicode(ticket2.id), relations[0]["destination"].id)

        self.assertEqual(0, len(self.get_relations(ticket2)))

    def test_can_add_multiple_relations(self):
        #arrange
        ticket = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        ticket3 = self._insert_and_load_ticket("A3")
        #act
        self.add_relation(ticket, DEPENDS_ON, ticket2)
        self.add_relation(ticket, DEPENDS_ON, ticket3)
        #assert
        self.assertEqual(2, len(self.get_relations(ticket)))
        self.assertEqual(1, len(self.get_relations(ticket2)))
        self.assertEqual(1, len(self.get_relations(ticket3)))

    def test_will_not_create_more_than_one_identical_relations(self):
        #arrange
        ticket = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        #act
        self.add_relation(ticket, DEPENDS_ON, ticket2)
        self.assertRaisesRegexp(
            TracError,
            "already exists",
            self.add_relation,
            ticket, DEPENDS_ON, ticket2
        )

    def test_will_not_create_more_than_one_identical_relations_db_level(self):
        sql = """INSERT INTO bloodhound_relations (source, destination, type)
                    VALUES (%s, %s, %s)"""
        with self.env.db_transaction as db:
            db(sql, ["1", "2", DEPENDS_ON])
            self.assertRaises(
                self.env.db_exc.IntegrityError,
                db,
                sql,
                ["1", "2", DEPENDS_ON]
            )

    def test_can_add_one_way_relations(self):
        #arrange
        ticket = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        #act
        self.add_relation(ticket, REFERS_TO, ticket2)
        #assert
        relations = self.get_relations(ticket)
        self.assertEqual(REFERS_TO, relations[0]["type"])
        self.assertEqual(unicode(ticket2.id),
                         relations[0]["destination"].id)

        self.assertEqual(0, len(self.get_relations(ticket2)))

    def test_can_delete_two_ways_relation(self):
        #arrange
        ticket = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        self.add_relation(ticket, DEPENDS_ON, ticket2)

        relations = self.get_relations(ticket)
        self.assertEqual(1, len(relations))
        self.assertEqual(1, len(self.get_relations(ticket2)))

        #act
        self.delete_relation(relations[0])
        #assert
        self.assertEqual(0, len(self.get_relations(ticket)))
        self.assertEqual(0, len(self.get_relations(ticket2)))

    def test_can_delete_single_way_relation(self):
        #arrange
        ticket = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        #act
        self.add_relation(ticket, REFERS_TO, ticket2)

        relations = self.get_relations(ticket)
        self.assertEqual(1, len(relations))
        self.assertEqual(0, len(self.get_relations(ticket2)))
        #act
        self.delete_relation(relations[0])
        #assert
        self.assertEqual(0, len(self.get_relations(ticket)))

    def test_can_not_add_cycled_immediate_relations(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        #act
        self.add_relation(ticket1, DEPENDS_ON, ticket2)

        try:
            self.add_relation(ticket2, DEPENDS_ON, ticket1)
            self.fail("Should throw an exception")
        except ValidationError as ex:
            self.assertSequenceEqual(
                ["tp1:ticket:2", "tp1:ticket:1"], ex.failed_ids)

    def test_can_add_more_depends_ons(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        ticket3 = self._insert_and_load_ticket("A3")
        #act
        self.add_relation(ticket1, DEPENDS_ON, ticket2)
        self.add_relation(ticket1, DEPENDS_ON, ticket3)

        self.assertEqual(2, len(self.get_relations(ticket1)))

    def test_can_not_add_cycled_in_different_direction(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        #act
        self.add_relation(ticket1, DEPENDS_ON, ticket2)
        self.assertRaises(
            ValidationError,
            self.add_relation,
            ticket1, DEPENDENCY_OF, ticket2
        )

    def test_can_not_add_cycled_relations(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        ticket3 = self._insert_and_load_ticket("A3")
        #act
        self.add_relation(ticket1, DEPENDS_ON, ticket2)
        self.add_relation(ticket2, DEPENDS_ON, ticket3)
        self.assertRaises(
            ValidationError,
            self.add_relation,
            ticket3, DEPENDS_ON, ticket1
        )

    def test_can_not_add_more_than_one_parent(self):
        #arrange
        child = self._insert_and_load_ticket("A1")
        parent1 = self._insert_and_load_ticket("A2")
        parent2 = self._insert_and_load_ticket("A3")
        #act
        self.add_relation(parent1, PARENT, child)
        self.assertRaises(
            ValidationError,
            self.add_relation,
            parent2, PARENT, child
        )

        self.assertRaises(
            ValidationError,
            self.add_relation,
            child, CHILD, parent2
        )

    def test_can_add_more_than_one_child(self):
        parent = self._insert_and_load_ticket("A1")
        child1 = self._insert_and_load_ticket("A2")
        child2 = self._insert_and_load_ticket("A3")

        self.add_relation(parent, PARENT, child1)
        self.add_relation(parent, PARENT, child2)
        self.assertEqual(2, len(self.get_relations(parent)))

    def test_ticket_can_be_resolved(self):
        #arrange
        parent = self._insert_and_load_ticket("A1")
        child = self._insert_and_load_ticket("A2")
        #act
        self.add_relation(parent, PARENT, child)

        self.req.args['action'] = 'resolve'
        warnings = \
            TicketRelationsSpecifics(self.env).validate_ticket(self.req, child)
        self.assertEqual(0, len(list(warnings)))

    def test_can_save_and_load_relation_time(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        #act
        time = datetime.now(utc)
        self.add_relation(ticket1, DEPENDS_ON, ticket2, when=time)
        relations = self.get_relations(ticket1)
        #assert
        self.assertEqual(time, relations[0]["when"])

    def test_cannot_resolve_ticket_when_blocker_is_unresolved(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        self.add_relation(ticket1, DEPENDS_ON, ticket2)
        #act
        self.req.args["action"] = 'resolve'
        warnings = TicketRelationsSpecifics(self.env).validate_ticket(
            self.req, ticket1)
        #asset
        self.assertEqual(1, len(list(warnings)))

    def test_can_resolve_ticket_when_blocker_is_resolved(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2", status="closed")
        self.add_relation(ticket1, DEPENDS_ON, ticket2)
        #act
        self.req.args["action"] = 'resolve'
        warnings = TicketRelationsSpecifics(self.env).validate_ticket(
            self.req, ticket1)
        #assert
        self.assertEqual(0, len(list(warnings)))

    def test_that_relations_are_deleted_when_ticket_is_deleted(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")

        self.add_relation(ticket1, DEPENDS_ON, ticket2)
        self.assertEqual(1, len(self.get_relations(ticket2)))
        #act
        ticket1.delete()
        #assert
        self.assertEqual(0, len(self.get_relations(ticket2)))

    def test_that_no_error_when_deleting_ticket_without_relations(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        #act
        ticket1.delete()

    def test_can_add_multi_product_relations(self):

        ticket1 = self._insert_and_load_ticket("A1")
        product2 = "tp2"
        self._load_product_from_data(self.global_env, product2)
        p2_env = ProductEnvironment(self.global_env, product2)
        ticket2 = self._insert_and_load_ticket_with_env(p2_env, "A2")

        self.add_relation(ticket1, MULTIPRODUCT_REL, ticket2)

        self.assertEqual(1, len(self.get_relations(ticket1)))
        self.assertEqual(1, len(self.get_relations(ticket2)))

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

    def test_parent_relation_is_incompatible_with_two_way_relations(self):
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        self.add_relation(ticket2, DEPENDS_ON, ticket1)

        self.assertRaises(
            ValidationError,
            self.add_relation,
            ticket1, PARENT, ticket2
        )
        self.assertRaises(
            ValidationError,
            self.add_relation,
            ticket1, CHILD, ticket2
        )

    def test_parent_relation_is_incompatible_with_one_way_relations(self):
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        self.add_relation(ticket1, REFERS_TO, ticket2)

        self.assertRaises(
            ValidationError,
            self.add_relation,
            ticket1, PARENT, ticket2
        )
        self.assertRaises(
            ValidationError,
            self.add_relation,
            ticket1, CHILD, ticket2
        )

    def test_parent_must_be_in_same_product(self):
        ticket1 = self._insert_and_load_ticket("A1")
        product2 = "tp2"
        self._load_product_from_data(self.global_env, product2)
        p2_env = ProductEnvironment(self.global_env, product2)
        ticket2 = self._insert_and_load_ticket_with_env(p2_env, "A2")

        self.assertRaises(
            ValidationError,
            self.add_relation,
            ticket1, PARENT, ticket2
        )
        self.assertRaises(
            ValidationError,
            self.add_relation,
            ticket1, CHILD, ticket2
        )

    def test_cannot_create_other_relations_between_descendants(self):
        t1, t2, t3, t4, t5 = map(self._insert_and_load_ticket, "12345")
        self.add_relation(t1, PARENT, t2)   #    t1 -> t2
        self.add_relation(t2, PARENT, t3)   #         /  \
        self.add_relation(t2, PARENT, t4)   #       t3    t4

        self.assertRaises(
            ValidationError,
            self.add_relation,
            t2, DEPENDS_ON, t1
        )
        self.assertRaises(
            ValidationError,
            self.add_relation,
            t1, DEPENDS_ON, t2
        )
        self.assertRaises(
            ValidationError,
            self.add_relation,
            t4, DEPENDS_ON, t1
        )
        self.assertRaises(
            ValidationError,
            self.add_relation,
            t1, DEPENDS_ON, t3
        )
        try:
            self.add_relation(t1, DEPENDS_ON, t5)
            self.add_relation(t3, DEPENDS_ON, t4)
        except ValidationError:
            self.fail("Could not add valid relation.")

    def test_cannot_add_parent_if_this_would_cause_invalid_relations(self):
        t1, t2, t3, t4, t5 = map(self._insert_and_load_ticket, "12345")
        self.add_relation(t1, PARENT, t2)   #    t1 -> t2
        self.add_relation(t2, PARENT, t3)   #         /  \
        self.add_relation(t2, PARENT, t4)   #       t3    t4    t5
        self.add_relation(t2, DEPENDS_ON, t5)

        self.assertRaises(
            ValidationError,
            self.add_relation,
            t2, PARENT, t5
        )
        self.assertRaises(
            ValidationError,
            self.add_relation,
            t3, PARENT, t5
        )
        self.assertRaises(
            ValidationError,
            self.add_relation,
            t5, PARENT, t1,
        )
        try:
            self.add_relation(t1, PARENT, t5)
        except ValidationError:
            self.fail("Could not add valid relation.")

    def test_cannot_close_ticket_with_open_children(self):
        t1 = self._insert_and_load_ticket("1")                    #     t1
        t2 = self._insert_and_load_ticket("2", status='closed')   #   /  |  \
        t3 = self._insert_and_load_ticket("3")                    #  t2 t3  t4
        t4 = self._insert_and_load_ticket("4")
        self.add_relation(t1, PARENT, t2)
        self.add_relation(t1, PARENT, t3)
        self.add_relation(t1, PARENT, t4)

        # A warning is be returned for each open ticket
        self.req.args["action"] = 'resolve'
        warnings = \
            TicketRelationsSpecifics(self.env).validate_ticket(self.req, t1)

        self.assertEqual(2, len(list(warnings)))

    def test_duplicate_can_only_reference_older_ticket(self):
        t1 = self._insert_and_load_ticket("1")
        t2 = self._insert_and_load_ticket("2")

        self.assertRaises(
            ValidationError,
            self.add_relation,
            t1, DUPLICATE_OF, t2
        )
        self.add_relation(t2, DUPLICATE_OF, t1)

    def test_detects_blocker_cycles(self):
        t1, t2, t3, t4, t5 = map(self._insert_and_load_ticket, "12345")
        self.add_relation(t1, BLOCKS, t2)
        self.add_relation(t3, DEPENDS_ON, t2)
        self.add_relation(t4, BLOCKED_BY, t3)
        self.add_relation(t4, DEPENDENCY_OF, t5)

        self.assertRaises(
            ValidationError,
            self.add_relation,
            t2, BLOCKS, t1
        )
        self.assertRaises(
            ValidationError,
            self.add_relation,
            t3, DEPENDENCY_OF, t1
        )
        self.assertRaises(
            ValidationError,
            self.add_relation,
            t1, BLOCKED_BY, t2
        )
        self.assertRaises(
            ValidationError,
            self.add_relation,
            t1, DEPENDS_ON, t5
        )

        self.add_relation(t1, DEPENDENCY_OF, t2)
        self.add_relation(t2, BLOCKS, t3)
        self.add_relation(t4, DEPENDS_ON, t3)
        self.add_relation(t5, BLOCKED_BY, t4)

        self.add_relation(t1, REFERS_TO, t2)
        self.add_relation(t2, REFERS_TO, t1)

    def test_can_find_ticket_by_id_from_same_env(self):
        """ Can find ticket given #id"""
        product2 = "tp2"
        self._load_product_from_data(self.global_env, product2)
        p2_env = ProductEnvironment(self.global_env, product2)
        t1 = self._insert_and_load_ticket_with_env(p2_env, "T1")
        trs = TicketRelationsSpecifics(p2_env)

        ticket = trs.find_ticket("#%d" % t1.id)

        self.assertEqual(ticket.id, 1)

    def test_can_find_ticket_by_id_from_different_env(self):
        """ Can find ticket from different env given #id"""
        product2 = "tp2"
        self._load_product_from_data(self.global_env, product2)
        p2_env = ProductEnvironment(self.global_env, product2)
        t1 = self._insert_and_load_ticket_with_env(p2_env, "T1")
        trs = TicketRelationsSpecifics(self.env)

        ticket = trs.find_ticket("#%d" % t1.id)

        self.assertEqual(ticket.id, 1)

    def test_can_find_ticket_by_product_and_id(self):
        """ Can find ticket given #prefix-id"""
        product2 = "tp2"
        self._load_product_from_data(self.global_env, product2)
        p2_env = ProductEnvironment(self.global_env, product2)
        t1 = self._insert_and_load_ticket_with_env(p2_env, "T1")
        trs = TicketRelationsSpecifics(self.env)

        ticket = trs.find_ticket("#%s-%d" % (product2, t1.id))

        self.assertEqual(ticket.id, 1)


class RelationChangingListenerTestCase(BaseRelationsTestCase):
    def test_can_sent_adding_event(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        test_changing_listener = self.env[TestRelationChangingListener]
        #act
        self.add_relation(ticket1, DEPENDS_ON, ticket2)
        #assert
        self.assertEqual("adding_relation", test_changing_listener.action)
        relation = test_changing_listener.relation
        self.assertEqual(DEPENDS_ON, relation.type)

    def test_can_sent_deleting_event(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        test_changing_listener = self.env[TestRelationChangingListener]
        self.add_relation(ticket1, DEPENDS_ON, ticket2)
        #act
        relations = self.get_relations(ticket1)
        self.delete_relation(relations[0])
        #assert
        self.assertEqual("deleting_relation", test_changing_listener.action)
        relation = test_changing_listener.relation
        self.assertEqual(DEPENDS_ON, relation.type)


class TicketChangeRecordUpdaterTestCase(BaseRelationsTestCase):
    def test_can_update_ticket_history_on_relation_add_on(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")
        #act
        self.add_relation(ticket1, DEPENDS_ON, ticket2)
        #assert
        change_log1 = Ticket(self.env, ticket1.id).get_changelog()
        self.assertEquals(1, len(change_log1))

        change_log2 = Ticket(self.env, ticket2.id).get_changelog()
        self.assertEquals(1, len(change_log2))

    def test_can_update_ticket_history_on_relation_deletion(self):
        #arrange
        ticket1 = self._insert_and_load_ticket("A1")
        ticket2 = self._insert_and_load_ticket("A2")

        self.add_relation(ticket1, DEPENDS_ON, ticket2)
        relations = self.get_relations(ticket1)
        #act
        self.delete_relation(relations[0])
        #assert
        change_log1 = Ticket(self.env, ticket1.id).get_changelog()
        self.assertEquals(2, len(change_log1))

        change_log2 = Ticket(self.env, ticket2.id).get_changelog()
        self.assertEquals(2, len(change_log2))

    def _debug_select(self, ticket_id=None):
        """
        used for debug purposes
        """
        # print " source, destination, type"
        sql = "SELECT * FROM ticket_change"
        print "db_direct_transaction result:"
        with self.env.db_direct_transaction as db:
            # for row in db(sql, ("source", "destination", "type")):
            for row in db(sql):
                print row

        sql = "SELECT * FROM ticket_change"
        print "db_transaction result:"
        with self.env.db_transaction as db:
            for row in db(sql):
                print row

        if ticket_id:
            sql = """SELECT time, author, field, oldvalue, newvalue
                     FROM ticket_change WHERE ticket=%s"""
            print "db_transaction select by ticket_id result:"
            with self.env.db_transaction:
                for row in self.env.db_query(sql, (ticket_id, )):
                    print row


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(ApiTestCase))
    test_suite.addTest(unittest.makeSuite(RelationChangingListenerTestCase))
    test_suite.addTest(unittest.makeSuite(TicketChangeRecordUpdaterTestCase))
    return test_suite


if __name__ == '__main__':
    unittest.main()
