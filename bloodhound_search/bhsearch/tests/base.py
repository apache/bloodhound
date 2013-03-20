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
import unittest
import tempfile
import shutil
from pprint import pprint

from bhsearch.web_ui import BloodhoundSearchModule
from trac.ticket import Ticket, Milestone
from trac.test import EnvironmentStub, Mock, MockPerm
from trac.web import Href, arg_list_to_args
from trac.wiki import WikiPage

BASE_PATH = "/main/"

class BaseBloodhoundSearchTest(unittest.TestCase):

    def setUp(self, enabled = None, create_req = False):
        if not enabled:
            enabled = ['trac.*', 'bhsearch.*']
        self.env = EnvironmentStub(enable=enabled)
        self.env.path = tempfile.mkdtemp('bhsearch-tempenv')
        self.env.config.set('bhsearch', 'silence_on_error', "False")
        if create_req:
            self.req = Mock(
                perm=MockPerm(),
                chrome={'logo': {}, 'links': {}},
                href=Href("/main"),
                base_path=BASE_PATH,
                path_info='/bhsearch',
                args=arg_list_to_args([]),
            )

    def tearDown(self):
        shutil.rmtree(self.env.path)
        self.env.reset_db()

    def print_result(self, result):
        print "Received result:"
        pprint(result.__dict__)

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
        ticket.insert()
        return ticket

    def create_wiki(self, name, text,  **kw):
        page = WikiPage(self.env, name)
        page.text = text
        for k, v in kw.items():
            page[k] = v
        return page

    def insert_wiki(self, name, text = None, **kw):
        text = text or "Dummy text"
        page = self.create_wiki(name, text, **kw)
        return page.save("dummy author", "dummy comment", "::1")

    def insert_milestone(self, name, description = None):
        milestone = self.create_milestone(
            name = name,
            description = description)
        milestone.insert()
        return milestone

    def create_milestone(self, name, description = None):
        milestone = Milestone(self.env)
        milestone.name = name
        if description is not None:
            milestone.description = description
        return milestone

    def change_milestone(self, name_to_change, name=None, description=None):
        milestone = Milestone(self.env, name_to_change)
        if name is not None:
            milestone.name = name
        if description is not None:
            milestone.description = description
        milestone.update()
        return milestone

    def process_request(self):
        # pylint: disable=unused-variable
        url, data, x = BloodhoundSearchModule(self.env).process_request(
            self.req)
        print "Received url: %s data:" % url
        pprint(data)
        if data.has_key("results"):
            print "results :"
            pprint(data["results"].__dict__)
        return data




