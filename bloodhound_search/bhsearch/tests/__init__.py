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

try:
    import unittest2 as unittest
except ImportError:
    import unittest

from bhsearch.tests import (whoosh_backend, index_with_whoosh, web_ui,
                            api, query_parser, query_suggestion, security)
from bhsearch.tests.search_resources import (ticket_search, wiki_search,
                                             milestone_search, base,
                                             changeset_search)


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(index_with_whoosh.suite())
    test_suite.addTest(whoosh_backend.suite())
    test_suite.addTest(web_ui.suite())
    test_suite.addTest(api.suite())
    test_suite.addTest(query_parser.suite())
    test_suite.addTest(query_suggestion.suite())
    test_suite.addTest(security.suite())
    test_suite.addTest(ticket_search.suite())
    test_suite.addTest(wiki_search.suite())
    test_suite.addTest(milestone_search.suite())
    test_suite.addTest(changeset_search.suite())
    test_suite.addTest(base.suite())
    return test_suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
else:
    test_suite = suite()
