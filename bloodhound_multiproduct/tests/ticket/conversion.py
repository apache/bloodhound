
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

"""Tests for Apache(TM) Bloodhound's MIME conversions for tickets in
product environments"""

import os.path
import unittest

from trac.test import Mock
from trac.mimeview.api import Mimeview
from trac.ticket.tests.conversion import TicketConversionTestCase
from trac.web.href import Href

from multiproduct.ticket.web_ui import ProductTicketModule
from multiproduct.env import ProductEnvironment
from tests.env import MultiproductTestCase

class ProductTicketConversionTestCase(TicketConversionTestCase, \
        MultiproductTestCase):

    def setUp(self):
        self._mp_setup()
        self.global_env = self.env
        self.env = ProductEnvironment(self.global_env, self.default_product)

        # Product name inserted in RSS feed
        self.env.product._data['name'] = 'My Project'

        self.env.config.set('trac', 'templates_dir',
                            os.path.join(os.path.dirname(self.env.path),
                                         'templates'))
        self.ticket_module = ProductTicketModule(self.env)
        self.mimeview = Mimeview(self.env)
        self.req = Mock(base_path='/trac.cgi', path_info='',
                        href=Href('/trac.cgi'), chrome={'logo': {}},
                        abs_href=Href('http://example.org/trac.cgi'),
                        environ={}, perm=[], authname='-', args={}, tz=None,
                        locale='', session=None, form_token=None)

    def test_csv_conversion(self):
        ticket = self._create_a_ticket()
        csv = self.mimeview.convert_content(self.req, 'trac.ticket.Ticket',
                                            ticket, 'csv')
        self.assertEqual(('\xef\xbb\xbf'
                          'id,summary,reporter,owner,description,status,'
                          'product,keywords,cc\r'
                          '\n1,Foo,santa,,Bar,,,,\r\n',
                          'text/csv;charset=utf-8', 'csv'), csv)

    def test_tab_conversion(self):
        ticket = self._create_a_ticket()
        csv = self.mimeview.convert_content(self.req, 'trac.ticket.Ticket',
                                            ticket, 'tab')
        self.assertEqual(('\xef\xbb\xbf'
                          'id\tsummary\treporter\towner\tdescription\tstatus\t'
                          'product\tkeywords\tcc\r\n'
                          '1\tFoo\tsanta\t\tBar\t\t\t\t\r\n',
                          'text/tab-separated-values;charset=utf-8', 'tsv'),
                         csv)

    def tearDown(self):
        self.global_env.reset_db()

def test_suite():
    return unittest.TestSuite([
            unittest.makeSuite(ProductTicketConversionTestCase,'test'),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

