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

import os

from trac.test import EnvironmentStub, Mock, MockPerm
from trac.web import Href, arg_list_to_args

from bhsearch.tests import unittest
from bhsearch.tests.base import BaseBloodhoundSearchTest
from bhsearch.web_ui import RequestParameters
from bhsearch.whoosh_backend import WhooshBackend
from whoosh import query


class RealIndexTestCase(BaseBloodhoundSearchTest):
    """
    This test case is not supposed to be run from CI tool.
    The purpose of the class is to work with real Bloodhound Search Index and
    should be used for debugging purposes only
    """
    def setUp(self):
        self.env = EnvironmentStub(enable=['bhsearch.*'])
        current_current_dir = os.getcwd()

        real_env_path = os.path.join(
            current_current_dir,
            "../../../installer/bloodhound/environments/main")
        self.env.path = real_env_path
        self.whoosh_backend = WhooshBackend(self.env)

        self.req = Mock(
            perm=MockPerm(),
            chrome={'logo': {}},
            href=Href("/main"),
            args=arg_list_to_args([]),
        )

    def test_read_all(self):
        result = self.whoosh_backend.query(
            query.Every()
        )
        self.print_result(result)

        result = self.whoosh_backend.query(
            query.Every()
        )
        self.print_result(result)
        self.assertLessEqual(1, result.hits)

    def test_read_with_type_facet(self):
        result = self.whoosh_backend.query(
            query.Every()
        )
        self.print_result(result)

        result = self.whoosh_backend.query(
            query.Every(),
            facets=["type"]
        )
        self.print_result(result)
        self.assertLessEqual(1, result.hits)

    def test_read_from_search_module(self):
        self.req.args[RequestParameters.QUERY] = "*"
        self.process_request()

def suite():
    pass

if __name__ == '__main__':
    unittest.main()
