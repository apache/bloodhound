# -*- coding: utf-8 -*-
#
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

from trac.web.href import Href

from multiproduct.hooks import ProductizedHref


class ProductizedHrefTestCase(unittest.TestCase):

    def setUp(self):
        self.ghref = Href('/gbase')
        self.phref = ProductizedHref(self.ghref, '/gbase/product')

    def test_paths_no_transform(self):
        self.assertEqual('/gbase/admin', self.phref.admin())
        self.assertEqual('/gbase/logout', self.phref.logout())
        self.assertEqual('/gbase/prefs', self.phref('prefs'))
        self.assertEqual('/gbase/verify_email?a=1&b=cde',
                         self.phref('verify_email', a=1, b='cde'))

    def test_static_path_no_transform(self):
        self.assertEqual('/gbase/js', self.phref('js/'))
        self.assertEqual('/gbase/css', self.phref('css/'))
        self.assertEqual('/gbase/img', self.phref('img/'))

    def test_params_as_args(self):
        self.assertEqual('/gbase/product/ticket/540',
                         self.phref('ticket', 540))
        self.assertEqual('/gbase/product/ticket/540',
                         self.phref.ticket(540))

    def test_params_as_kwargs(self):
        self.assertIn(self.phref('ticket', param='value',
                                 other='other value'),
                      ['/gbase/product/ticket?param=value&other=other+value',
                       '/gbase/product/ticket?other=other+value&param=value'])

    def test_params_as_dictionary(self):
        self.assertIn(self.phref.ticket({'param': 'value',
                                         'other': 'other value'}),
                      ['/gbase/product/ticket/?param=value&other=other+value',
                       '/gbase/product/ticket?other=other+value&param=value'])


def test_suite():
    return unittest.TestSuite([
        unittest.makeSuite(ProductizedHrefTestCase, 'test')
    ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
