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
import difflib
import pkg_resources

from trac.test import EnvironmentStub
from bhsolr.schema import SolrSchema


class SolrSchemaTestCase(unittest.TestCase):
    def setUp(self):

        self.env = EnvironmentStub(enable=('trac.*', 'bhsolr.*'))
        resource_filename = pkg_resources.resource_filename
        self.data_path = resource_filename(__name__,
                                           "/data/schema_test_file.xml")
        self.test_path = "/Users/antonia/Desktop"
        self.schema = SolrSchema(self.env)

    def test_generates_schema_correctly(self):
        self.schema.generate_schema(path=self.test_path)

        print self.data_path
        with open(self.data_path, 'r') as hosts0:
            with open(self.test_path + "/schema.xml", 'r') as hosts1:
                diff = difflib.unified_diff(
                    hosts0.readlines(),
                    hosts1.readlines(),
                    fromfile='schema_test_file.xml',
                    tofile='schema.xml',
                    )

                for line in diff:
                    self.assertEqual(line, "",
                                     "The schema.xml file is not valid.")

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(SolrSchemaTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
