
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
import unittest
import tempfile
import shutil

from sqlite3 import OperationalError

from trac.test import EnvironmentStub
from trac.core import TracError

from multiproduct.model import Product
from multiproduct.api import MultiProductSystem

class ProductTestCase(unittest.TestCase):
    """Unit tests covering the Product model"""
    def setUp(self):
        self.env = EnvironmentStub(enable=['trac.*', 'multiproduct.*'])
        self.env.path = tempfile.mkdtemp('bh-product-tempenv')
        
        self.mpsystem = MultiProductSystem(self.env)
        try:
            self.mpsystem.upgrade_environment(self.env.db_transaction)
        except OperationalError:
            # table remains but database version is deleted
            pass
        
        self.default_data = {'prefix':'tp',
                             'name':'test project',
                             'description':'a test project'}
        
        product = Product(self.env)
        product._data.update(self.default_data)
        product.insert()
    
    def tearDown(self):
        shutil.rmtree(self.env.path)
        self.env.reset_db()
    
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
        products = list(Product.select(self.env, where={'name':'test project'}))
        self.assertEqual(1, len(products))
        products = list(Product.select(self.env, where={'prefix':'tp3',
                                                        'name':'test project 3'}))
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

if __name__ == '__main_':
    unittest.main()

