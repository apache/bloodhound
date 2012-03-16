
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
from trac.util.subclasses import subclasses

class BaseClass(object):
    """Common base class for tests"""
class SubClass(BaseClass):
    """Common sub class of BaseClass for tests"""

class SubClassTestCase(unittest.TestCase):
    def test_discover_subclass(self):
        subs = list(subclasses(BaseClass))
        self.assertEqual(len(subs), 1)
        self.assertIs(subs[0], SubClass)

    def test_discover_subsubclass(self):
        class SubSubClass(SubClass):
            """Sub class of SubClass"""
        subs = list(subclasses(BaseClass))
        self.assertEqual(len(subs), 2)
        self.assertIn(SubClass, subs)
        self.assertIn(SubSubClass, subs)

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(SubClassTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
