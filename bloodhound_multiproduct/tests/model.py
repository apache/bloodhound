
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

"""Tests for multiproduct/model.py"""
import shutil
import sys
import tempfile

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from sqlite3 import OperationalError

from trac.test import EnvironmentStub
from trac.core import TracError
from trac.ticket.model import Ticket

from multiproduct.env import ProductEnvironment
from multiproduct.model import Product
from bhdashboard.model import ModelBase

from multiproduct.api import MultiProductSystem
from trac.tests.resource import TestResourceChangeListener


class ProductTestCase(unittest.TestCase):
    """Unit tests covering the Product model"""
    INITIAL_PREFIX = 'tp'
    INITIAL_NAME = 'test project'
    INITIAL_DESCRIPTION = 'a test project'

    def setUp(self):
        self.env = EnvironmentStub(enable=['trac.*', 'multiproduct.*'])
        self.env.path = tempfile.mkdtemp('bh-product-tempenv')
        
        self.mpsystem = MultiProductSystem(self.env)
        try:
            self.mpsystem.upgrade_environment(self.env.db_transaction)
        except OperationalError:
            # table remains but database version is deleted
            pass
        
        self.listener = self._enable_resource_change_listener()
        self.default_data = {'prefix':self.INITIAL_PREFIX,
                             'name':self.INITIAL_NAME,
                             'description':self.INITIAL_DESCRIPTION}

        self.global_env = self.env
        self.product = Product(self.env)
        self.product._data.update(self.default_data)
        self.product.insert()

    def tearDown(self):
        shutil.rmtree(self.env.path)
        self.env.reset_db()
    
    def _enable_resource_change_listener(self):
        listener = TestResourceChangeListener(self.env)
        listener.resource_type = Product
        listener.callback = self.listener_callback
        return listener

    def listener_callback(self, action, resource, context, old_values = None):
        # pylint: disable=unused-argument
        # pylint: disable=attribute-defined-outside-init
        self.prefix = resource.prefix
        self.name = resource.name
        self.description = resource.description

    def test_set_table_field(self):
        """tests that table.field style update works"""
        test = {'prefix': 'td',
                'name': 'test field access',
                'description': 'product to test field setting'}
        
        product = Product(self.env)
        
        # attempt to set the fields from the data
        product.prefix = test['prefix']
        product.name = test['name']
        product.description = test['description']
        
        self.assertEqual(product._data['prefix'], test['prefix'])
        self.assertEqual(product._data['name'], test['name'])
        self.assertEqual(product._data['description'], test['description'])
    
    def test_select(self):
        """tests that select can search Products by fields"""
        
        p2_data = {'prefix':'tp2',
                   'name':'test project 2',
                   'description':'a different test project'}
        p3_data = {'prefix':'tp3',
                   'name':'test project 3',
                   'description':'test project'}
        
        product2 = Product(self.env)
        product2._data.update(p2_data)
        product3 = Product(self.env)
        product3._data.update(p3_data)
        
        product2.insert()
        product3.insert()
        
        products = list(Product.select(self.env, where={'prefix':'tp'}))
        self.assertEqual(1, len(products))
        products = list(Product.select(self.env,
            where={'name':'test project'}))
        self.assertEqual(1, len(products))
        products = list(Product.select(self.env,
            where={'prefix':'tp3', 'name':'test project 3'}))
        self.assertEqual(1, len(products))
    
    def test_update(self):
        """tests that we can use update to push data to the database"""
        product = list(Product.select(self.env, where={'prefix':'tp'}))[0]
        self.assertEqual('test project', product._data['name'])
        
        new_data = {'prefix':'tp', 
                    'name':'updated', 
                    'description':'nothing'}
        product._data.update(new_data)
        product.update()
        
        comp_product = list(Product.select(self.env, where={'prefix':'tp'}))[0]
        self.assertEqual('updated', comp_product._data['name'])
    
    def test_update_key_change(self):
        """tests that we raise an error for attempting to update key fields"""
        bad_data = {'prefix':'tp0', 
                    'name':'update', 
                    'description':'nothing'}
        product = list(Product.select(self.env, where={'prefix':'tp'}))[0]
        product._data.update(bad_data)
        self.assertRaises(TracError, product.update)
    
    def test_insert(self):
        """test saving new Product"""
        data = {'prefix':'new', 'name':'new', 'description':'new'}
        product = Product(self.env)
        product._data.update(data)
        product.insert()
        
        check_products = list(Product.select(self.env, where={'prefix':'new'}))
        
        self.assertEqual(product._data['prefix'],
                         check_products[0]._data['prefix'])
        self.assertEqual(1, len(check_products))
    
    def test_insert_duplicate_key(self):
        """test attempted saving of Product with existing key fails"""
        dupe_key_data = {'prefix':'tp',
                         'name':'dupe',
                         'description':'dupe primary key'}
        product2 = Product(self.env)
        product2._data.update(dupe_key_data)
        self.assertRaises(TracError, product2.insert)
    
    def test_delete(self):
        """test that we are able to delete Products"""
        product = list(Product.select(self.env, where={'prefix':'tp'}))[0]
        product.delete()
        
        post = list(Product.select(self.env, where={'prefix':'tp'}))
        self.assertEqual(0, len(post))
        
    def test_delete_twice(self):
        """test that we error when deleting twice on the same key"""
        product = list(Product.select(self.env, where={'prefix':'tp'}))[0]
        product.delete()
        
        self.assertRaises(TracError, product.delete)
    
    def test_field_data_get(self):
        """tests that we can use table.field syntax to get to the field data"""
        prefix = self.default_data['prefix']
        name = self.default_data['name']
        description = self.default_data['description']
        product = list(Product.select(self.env, where={'prefix':prefix}))[0]
        self.assertEqual(prefix, product.prefix)
        self.assertEqual(name, product.name)
        self.assertEqual(description, product.description)
    
    def test_field_set(self):
        """tests that we can use table.field = something to set field data"""
        prefix = self.default_data['prefix']
        product = list(Product.select(self.env, where={'prefix':prefix}))[0]
        
        new_description = 'test change of description'
        product.description = new_description
        self.assertEqual(new_description, product.description)

    def test_missing_unique_fields(self):
        """ensure that that insert method works when _meta does not specify
        unique fields when inserting more than one ProductResourceMap instances
        """
        class TestModel(ModelBase):
            """A test model with no unique_fields"""
            _meta = {'table_name': 'bloodhound_testmodel',
                     'object_name': 'TestModelObject',
                     'key_fields': ['id',],
                     'non_key_fields': ['value'],
                     'unique_fields': [],}

        from trac.db import DatabaseManager
        schema = [TestModel._get_schema(), ]
        with self.env.db_transaction as db:
            db_connector, dummy = DatabaseManager(self.env)._get_connector()
            for table in schema:
                for statement in db_connector.to_sql(table):
                    db(statement)
        
        structure =  dict([(table.name, [col.name for col in table.columns])
                           for table in schema])
        tm1 = TestModel(self.env)
        tm1._data.update({'id':1, 'value':'value1'})
        tm1.insert()
        tm2 = TestModel(self.env)
        tm2._data.update({'id':2, 'value':'value2'})
        tm2.insert()

    def test_change_listener_created(self):
        self.assertEqual('created', self.listener.action)
        self.assertIsInstance(self.listener.resource, Product)
        self.assertEqual(self.INITIAL_PREFIX, self.prefix)
        self.assertEqual(self.INITIAL_NAME, self.name)
        self.assertEqual(self.INITIAL_DESCRIPTION, self.description)

    def test_change_listener_changed(self):
        CHANGED_NAME = "changed name"
        self.product.name = CHANGED_NAME
        self.product.update()
        self.assertEqual('changed', self.listener.action)
        self.assertIsInstance(self.listener.resource, Product)
        self.assertEqual(CHANGED_NAME, self.name)
        self.assertEqual({"name":self.INITIAL_NAME}, self.listener.old_values)

    def test_change_listener_deleted(self):
        self.product.delete()
        self.assertEqual('deleted', self.listener.action)
        self.assertIsInstance(self.listener.resource, Product)
        self.assertEqual(self.INITIAL_PREFIX, self.prefix)

    def test_get_tickets(self):
        for pdata in (
            {'prefix': 'p2', 'name':'product, too', 'description': ''},
            {'prefix': 'p3', 'name':'strike three', 'description': ''},
        ):
            num_tickets = 5
            product = Product(self.global_env)
            product._data.update(pdata)
            product.insert()
            self.env = ProductEnvironment(self.global_env, product)
            for i in range(num_tickets):
                ticket = Ticket(self.env)
                ticket['summary'] = 'hello ticket #%s-%d' % (product.prefix, i)
                ticket['reporter'] = 'admin'
                tid = ticket.insert()

            # retrieve tickets using both global and product scope
            tickets_from_global = [(t['product'], t['id']) for t in
                Product.get_tickets(self.global_env, product.prefix)]
            self.assertEqual(len(tickets_from_global), num_tickets)
            tickets_from_product = [(t['product'], t['id']) for t in
                Product.get_tickets(self.env)]
            self.assertEqual(len(tickets_from_product), num_tickets)
            # both lists should contain same elements
            intersection = set(tickets_from_global) & set(tickets_from_product)
            self.assertEqual(len(intersection), num_tickets)

def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(ProductTestCase, 'test'))
    return test_suite

if __name__ == '__main__':
    unittest.main()

