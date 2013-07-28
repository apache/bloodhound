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
from trac.tests.notification import SMTPServerStore, SMTPThreadedServer
from trac.ticket.tests.notification import (
    SMTP_TEST_PORT, smtp_address, parse_smtp_message)
from bhrelations.tests.base import BaseRelationsTestCase
from bhrelations.notification import RelationNotifyEmail


class NotificationTestCase(BaseRelationsTestCase):
    @classmethod
    def setUpClass(cls):
        cls.smtpd = CustomSMTPThreadedServer(SMTP_TEST_PORT)
        cls.smtpd.start()

    @classmethod
    def tearDownClass(cls):
        cls.smtpd.stop()

    def setUp(self):
        super(NotificationTestCase, self).setUp()
        self.env.config.set('notification', 'smtp_enabled', 'true')
        self.env.config.set('notification', 'always_notify_owner', 'true')
        self.env.config.set('notification', 'always_notify_reporter', 'true')
        self.env.config.set('notification', 'smtp_always_cc',
                            'joe.user@example.net, joe.bar@example.net')
        self.env.config.set('notification', 'use_public_cc', 'true')
        self.env.config.set('notification', 'smtp_port', str(SMTP_TEST_PORT))
        self.env.config.set('notification', 'smtp_server', 'localhost')
        self.notifier = RelationNotifyEmail(self.env)

    def tearDown(self):
        super(NotificationTestCase, self).tearDown()
        self.smtpd.cleanup()

    def test_recipients_of_both_related_tickets_get_notified(self):
        """To/Cc recipients"""
        ticket = self._insert_and_load_ticket(
            'Foo',
            reporter= '"Joe User" < joe.user@example.org >',
            owner='joe.user@example.net',
            cc='joe.user@example.com, joe.bar@example.org, '
               'joe.bar@example.net'
        )
        ticket2 = self._insert_and_load_ticket(
            'Bar',
            reporter='"Bob User" < bob.user@example.org >',
            owner='bob.user@example.net',
            cc='bob.user@example.com, bob.bar@example.org, '
               'bob.bar@example.net')
        relation = self.relations_system.add(
            ticket, ticket2, "dependent")

        rn = RelationNotifyEmail(self.env)
        rn.notify(relation)

        recipients = self.smtpd.get_recipients()
        # checks there is no duplicate in the recipient list
        rcpts = []
        for r in recipients:
            self.failIf(r in rcpts)
            rcpts.append(r)
        # checks that all cc recipients have been notified
        cc_list = self.env.config.get('notification', 'smtp_always_cc')
        cc_list = "%s, %s, %s" % (cc_list, ticket['cc'], ticket2['cc'])
        for r in cc_list.replace(',', ' ').split():
            self.failIf(r not in recipients)
        # checks that both owners have been notified
        self.failIf(smtp_address(ticket['owner']) not in recipients)
        self.failIf(smtp_address(ticket2['owner']) not in recipients)
        # checks that both reporters have been notified
        self.failIf(smtp_address(ticket['reporter']) not in recipients)
        self.failIf(smtp_address(ticket2['reporter']) not in recipients)

    def test_no_recipient_results_in_no_notification(self):
        self.env.config.set('notification', 'smtp_always_cc', '')
        ticket = self._insert_and_load_ticket('Foo', reporter='anonymous')
        ticket2 = self._insert_and_load_ticket('Bar', reporter='anonymous')

        self.relations_system.add(ticket, ticket2, "dependent")

        sender = self.smtpd.get_sender()
        recipients = self.smtpd.get_recipients()
        message = self.smtpd.get_message()
        # checks that no message has been sent
        self.failIf(recipients)
        self.failIf(sender)
        self.failIf(message)

    def test_one_email_per_relation(self):
        ticket = self._insert_and_load_ticket('Foo', reporter='anonymous')
        ticket2 = self._insert_and_load_ticket('Bar', reporter='anonymous')

        relation = self.relations_system.add(ticket, ticket2, "dependent")

        relations = self.env.db_direct_query(
            "SELECT * FROM bloodhound_relations")
        self.assertEqual(len(relations), 2)
        self.assertEqual(self.smtpd.messages_received(), 1)

        self.smtpd.cleanup()

        self.relations_system.delete(relation.get_relation_id())
        relations = self.env.db_direct_query(
            "SELECT * FROM bloodhound_relations")
        self.assertEqual(len(relations), 0)
        self.assertEqual(self.smtpd.messages_received(), 1)


class CustomSMTPServerStore(SMTPServerStore):
    """SMTPServerStore that can count received messages"""
    def __init__(self):
        SMTPServerStore.__init__(self)
        self.messages = 0

    def helo(self, args):
        SMTPServerStore.helo(self, args)
        self.messages += 1


class CustomSMTPThreadedServer(SMTPThreadedServer):
    def __init__(self, port):
        SMTPThreadedServer.__init__(self, port)
        self.store = CustomSMTPServerStore()

    def cleanup(self):
        SMTPThreadedServer.cleanup(self)
        self.store.messages = 0

    def messages_received(self):
        return self.store.messages


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(NotificationTestCase, 'test'))
    return test_suite

if __name__ == '__main__':
    unittest.main()
