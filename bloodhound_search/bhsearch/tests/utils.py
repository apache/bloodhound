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

r"""
Test utils methods
"""
import pprint
import unittest
from trac.ticket import Ticket
from trac.wiki import WikiPage

class BaseBloodhoundSearchTest(unittest.TestCase):
    def print_result(self, result):
        print "Received result:"
        pprint.pprint(result.__dict__)

    def create_dummy_ticket(self, summary = None):
        if not summary:
            summary = 'Hello World'
        data = {'component': 'foo', 'milestone': 'bar'}
        return self.create_ticket(summary, reporter='john', **data)

    def create_ticket(self, summary, **kw):
        ticket = Ticket(self.env)
        ticket["summary"] = summary
        for k, v in kw.items():
            ticket[k] = v
        return ticket

    def insert_ticket(self, summary, **kw):
        """Helper for inserting a ticket into the database"""
        ticket = self.create_ticket(summary, **kw)
        return ticket.insert()

    def create_wiki(self, name, text,  **kw):
        page = WikiPage(self.env, name)
        page.text = text
        for k, v in kw.items():
            page[k] = v
        return page

    def insert_wiki(self, name, text = None, **kw):
        """Helper for inserting a ticket into the database"""
        text = text or "Dummy text"
        page = self.create_wiki(name, text, **kw)
        return page.save("dummy author", "dummy comment", "::1")

