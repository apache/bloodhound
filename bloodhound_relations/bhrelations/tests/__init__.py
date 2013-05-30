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

# import sys
# if sys.version < (2, 7):
#     import unittest2 as unittest
# else:
#     import unittest
import unittest

from bhrelations.tests import api, notification, search, validation, web_ui


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(api.suite())
    test_suite.addTest(notification.suite())
    test_suite.addTest(search.suite())
    test_suite.addTest(validation.suite())
    test_suite.addTest(web_ui.suite())
    return test_suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
else:
    test_suite = suite()

