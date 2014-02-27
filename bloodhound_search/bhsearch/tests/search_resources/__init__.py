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

from bhsearch.tests import unittest
from bhsearch.tests.search_resources import base, changeset_search, \
    milestone_search, ticket_search, wiki_search


def suite():
    suite = unittest.TestSuite()
    suite.addTest(base.suite())
    suite.addTest(changeset_search.suite())
    suite.addTest(milestone_search.suite())
    suite.addTest(ticket_search.suite())
    suite.addTest(wiki_search.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
