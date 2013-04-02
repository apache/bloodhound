
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

"""Tests for inherited Apache(TM) Bloodhound's wiki macros 
in product environments"""

import os.path
import re
import unittest

from trac.wiki.tests import macros

from multiproduct.env import ProductEnvironment
from tests.env import MultiproductTestCase
from tests.wiki import formatter

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(formatter.test_suite(
                                  macros.IMAGE_MACRO_TEST_CASES, 
                                  file=macros.__file__))
    suite.addTest(formatter.test_suite(
                                  macros.TITLEINDEX1_MACRO_TEST_CASES, 
                                  file=macros.__file__))
    suite.addTest(formatter.test_suite(
                                  macros.TITLEINDEX2_MACRO_TEST_CASES, 
                                  file=macros.__file__,
                                  setup=macros.titleindex2_setup,
                                  teardown=macros.titleindex_teardown))
    suite.addTest(formatter.test_suite(
                                  macros.TITLEINDEX3_MACRO_TEST_CASES, 
                                  file=macros.__file__,
                                  setup=macros.titleindex3_setup,
                                  teardown=macros.titleindex_teardown))
    suite.addTest(formatter.test_suite(
                                  macros.TITLEINDEX4_MACRO_TEST_CASES, 
                                  file=macros.__file__,
                                  setup=macros.titleindex4_setup,
                                  teardown=macros.titleindex_teardown))
    suite.addTest(formatter.test_suite(
                                  macros.TITLEINDEX5_MACRO_TEST_CASES, 
                                  file=macros.__file__,
                                  setup=macros.titleindex5_setup,
                                  teardown=macros.titleindex_teardown))
    suite.addTest(formatter.test_suite(
                                  macros.RECENTCHANGES_MACRO_TEST_CASES, 
                                  file=macros.__file__,
                                  setup=macros.recentchanges_setup,
                                  teardown=macros.recentchanges_teardown))
    suite.addTest(formatter.test_suite(
                                  macros.TRACINI_MACRO_TEST_CASES, 
                                  file=macros.__file__,
                                  setup=macros.tracini_setup,
                                  teardown=macros.tracini_teardown))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

