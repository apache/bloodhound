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

from bhrelations.validation import Validator
from bhrelations.tests.base import BaseRelationsTestCase


class GraphFunctionsTestCase(BaseRelationsTestCase):
    edges = [
        ('A', 'B', 'p'),  #      A    H
        ('A', 'C', 'p'),  #     /  \ /
        ('C', 'D', 'p'),  #    B    C
        ('C', 'E', 'p'),  #        /  \
        ('E', 'F', 'p'),  #       D    E - F - G
        ('F', 'G', 'p'),  #
        ('H', 'C', 'p'),
    ]

    def setUp(self):
        BaseRelationsTestCase.setUp(self)
        # bhrelations point from destination to source
        for destination, source, type in self.edges:
            self.env.db_direct_transaction(
                """INSERT INTO bloodhound_relations (source, destination, type)
                        VALUES ('%s', '%s', '%s')""" %
                (source, destination, type)
            )
        self.validator = Validator(self.env)

    def test_find_path(self):
        self.assertEqual(
            self.validator._find_path(u'A', u'E', u'p'),
            [u'A', u'C', u'E'])
        self.assertEqual(
            self.validator._find_path(u'A', u'G', u'p'),
            [u'A', u'C', u'E', u'F', u'G'])
        self.assertEqual(
            self.validator._find_path(u'H', u'D', u'p'),
            [u'H', u'C', u'D'])
        self.assertEqual(
            self.validator._find_path(u'E', u'A', u'p'),
            None)
        self.assertEqual(
            self.validator._find_path(u'B', u'D', u'p'),
            None)

    def test_descendants(self):
        self.assertEqual(
            self.validator._descendants(u'B', u'p'),
            set()
        )
        self.assertEqual(
            self.validator._descendants(u'E', u'p'),
            set([u'F', u'G'])
        )
        self.assertEqual(
            self.validator._descendants(u'H', u'p'),
            set([u'C', u'D', u'E', u'F', u'G'])
        )

    def test_ancestors(self):
        self.assertEqual(
            self.validator._ancestors(u'B', u'p'),
            set([u'A'])
        )
        self.assertEqual(
            self.validator._ancestors(u'E', u'p'),
            set([u'A', u'C', u'H'])
        )
        self.assertEqual(
            self.validator._ancestors(u'H', u'p'),
            set()
        )


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(GraphFunctionsTestCase, 'test'))
    return test_suite

if __name__ == '__main__':
    unittest.main()
