
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

"""Models to support multi-product"""
from datetime import datetime
from itertools import izip

from trac.core import TracError
from trac.resource import Resource
from trac.ticket.model import Ticket
from trac.ticket.query import Query
from trac.util.datefmt import utc

from bhdashboard.model import ModelBase

# -------------------------------------------
# Product API
# -------------------------------------------


class Product(ModelBase):
    """The Product table"""
    _meta = {'table_name':'bloodhound_product',
            'object_name':'Product',
            'key_fields':['prefix',],
            'non_key_fields':['name', 'description', 'owner'],
            'no_change_fields':['prefix',],
            'unique_fields':['name'],
            }

    @property
    def resource(self):
        """Allow Product to be treated as a Resource"""
        return Resource('product', self.prefix)

    def delete(self, resources_to=None):
        """ override the delete method so that we can move references to this
        object to a new product """
        if resources_to is not None:
            new_product = Product(self._env, resources_to)
            if not new_product._exists:
                sdata = {'new_table':resources_to}
                sdata.update(self._meta)
                raise TracError('%(object_name)s %(new_table)s does not exist' %
                                sdata)
        original_prefix = self._data['prefix']
        super(Product, self).delete()
        #find and update all resources that should move
        where = {'product_id':original_prefix}
        for prm in ProductResourceMap.select(self._env, where=where):
            prm._data['product_id'] = resources_to
            prm.update()

    def _update_relations(self, db=None, author=None):
        """Extra actions due to update"""
        # tickets need to be updated
        old_name = self._old_data['name']
        new_name = self._data['name']
        now = datetime.now(utc)
        comment = 'Product %s renamed to %s' % (old_name, new_name)
        if old_name != new_name:
            for t in Product.get_tickets(self._env, self._data['prefix']):
                ticket = Ticket(self._env, t['id'], db)
                ticket.save_changes(author, comment, now)

    @classmethod
    def get_tickets(cls, env, product=''):
        """Retrieve all tickets associated with the product."""
        from multiproduct.ticket.query import ProductQuery
        from multiproduct.env import ProductEnvironment
        if not product and isinstance(env, ProductEnvironment):
            product = env.product.prefix
        q = ProductQuery.from_string(env, 'product=%s' % product)
        return q.execute()

class ProductResourceMap(ModelBase):
    """Table representing the mapping of resources to their product"""
    _meta = {'table_name':'bloodhound_productresourcemap',
            'object_name':'ProductResourceMapping',
            'key_fields':['id',],
            'non_key_fields':['product_id','resource_type','resource_id',],
            'no_change_fields':['id',],
            'unique_fields':[],
            'auto_inc_fields': ['id'],
            }

    def reparent_resource(self, product=None):
        """a specific function to update a record when it is to move product"""
        if product is not None:
            new_product = Product(self._env, product)
            if not new_product._exists:
                sdata = {'new_table':product}
                sdata.update(self.meta)
                raise TracError('%(object_name)s %(new_table)s does not exist' %
                                sdata)
        self._data['product_id'] = product
        self.update()

# -------------------------------------------
# Configuration
# -------------------------------------------

class ProductSetting(ModelBase):
    """The Product configuration table
    """
    _meta = {'table_name':'bloodhound_productconfig',
            'object_name':'ProductSetting',
            'key_fields':['product', 'section', 'option'],
            'non_key_fields':['value', ],
            'no_change_fields':['product', 'section', 'option'],
            'unique_fields':[],
            }

    @classmethod
    def exists(cls, env, product, section=None, option=None, db=None):
        """Determine whether there are configuration values for
        product, section, option .
        """
        if product is None:
            raise ValueError("Product prefix required")
        l = locals()
        option_subkey = ([c, l[c]] for c in ('product', 'section', 'option'))
        option_subkey = dict(c for c in option_subkey if c[1] is not None)
        return len(cls.select(env, db, where=option_subkey, limit=1)) > 0

    @classmethod
    def get_sections(cls, env, product):
        """Retrieve configuration sections defined for a product
        """
        # FIXME: Maybe something more ORM-ish should be added in ModelBase
        return [row[0] for row in env.db_query("""SELECT DISTINCT section 
                FROM bloodhound_productconfig WHERE product = %s""", 
                (product,)) ]

