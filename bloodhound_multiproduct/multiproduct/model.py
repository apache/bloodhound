
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
from trac.core import Component, TracError, implements
from trac.resource import ResourceNotFound
from trac.db import Table, Column, DatabaseManager
from trac.env import IEnvironmentSetupParticipant
from trac.resource import Resource

DB_VERSION = 1
DB_SYSTEM_KEY = 'bloodhound_multi_product_version'
PLUGIN_NAME = 'Bloodhound multi product'

class ModelBase(object):
    """Base class for the models to factor out common features
    Derived classes should provide a meta dictionary to describe the table like:
    
    _meta = {'table_name':'mytable',
             'object_name':'WhatIWillCallMyselfInMessages',
             'key_fields':['id','id2'],
             'non_key_fields':['thing','anotherthing'],
             }
    """
    
    def __init__(self, env, keys=None):
        """Initialisation requires an environment to be specified.
        If keys are provided, the Model will initialise from the database
        """
        # make this impossible to instantiate without telling the class details
        # about itself in the self.meta dictionary
        self._old_data = {}
        self._data = {}
        self._exists = False
        self._env = env
        self._all_fields = self._meta['key_fields'] + \
                           self._meta['non_key_fields']
        if keys is not None:
            self._get_row(keys)
        else:
            self._update_from_row(None)
    
    def update_field_dict(self, field_dict):
        """Updates the object's copy of the db fields (no db transaction)"""
        self._data.update(field_dict)
    
    def __getattr__(self, name):
        """Overridden to allow table.field style field access."""
        try:
            if name in self._all_fields:
                return self._data[name]
        except KeyError:
            raise AttributeError(name)
        raise AttributeError(name)
    
    def __setattr__(self, name, value):
        """Overridden to allow table.field = value style field setting."""
        data = self.__dict__.get('data')
        fields = self.__dict__.get('fields')
        
        if data and fields and name in fields:
            self._data[name] = value
        else:
            dict.__setattr__(self, name, value)
            
    
    def _update_from_row(self, row = None):
        """uses a provided database row to update the model"""
        fields = self._meta['key_fields']+self._meta['non_key_fields']
        self._exists = row is not None
        if row is None:
            row = [None]*len(fields)
        self._data = dict([(fields[i], row[i]) for i in range(len(row))])
        self._old_data = {}
        self._old_data.update(self._data)
    
    def _get_row(self, keys):
        """queries the database and stores the result in the model"""
        row = None
        key_fields = self._meta['key_fields']
        where = ','.join(['%s="%s"' % (k, keys[k]) for k in key_fields])
        fields = ','.join(self._meta['key_fields']+self._meta['non_key_fields'])
        sdata = {'fields':fields,
                 'where':where}
        sdata.update(self._meta)
        
        sql = """SELECT %(fields)s FROM %(table_name)s
                 WHERE %(where)s""" % sdata
        with self._env.db_query as db:
            for row in db(sql):
                self._update_from_row(row)
                break
            else:
                raise ResourceNotFound('No %(object_name)s with %(where)s' %
                                sdata)
    
    def delete(self):
        """Deletes the matching record from the database"""
        if not self._exists:
            raise TracError('%(object_name)s does not exist' % self._meta)
        sdata = {'where':','.join(['%s="%s"' % (k, self._data[k])
                                   for k in self._meta['key_fields']])}
        sdata.update(self._meta)
        sql = """DELETE FROM %(table_name)s
                 WHERE %(where)s""" % sdata
        with self._env.db_transaction as db:
            db(sql)
            self._exists = False
            self._data = dict([(k, None) for k in self._data.keys()])
            self._old_data.update(self._data)
    
    def insert(self):
        """Create new record in the database"""
        if self._exists or len(self.select(self._env, where =
                                dict([(k,self._data[k])
                                      for k in self._meta['key_fields']]))):
            sdata = {'keys':','.join(['%s="%s"' % (k, self._data[k])
                                     for k in self._meta['key_fields']])}
            sdata.update(self._meta)
            raise TracError('%(object_name)s %(keys)s already exists' %
                            sdata)
            
        for key in self._meta['key_fields']:
            if not self._data[key]:
                sdata = {'key':key}
                sdata.update(self._meta)
                raise TracError('%(key)s required for %(object_name)s' %
                                sdata)
        fields = self._meta['key_fields']+self._meta['non_key_fields']
        sdata = {'fields':','.join(fields),
                 'values':','.join(['"%s"' % self._data[f] for f in fields])}
        sdata.update(self._meta)
        
        sql = """INSERT INTO %(table_name)s (%(fields)s)
                 VALUES (%(values)s)""" % sdata
        with self._env.db_transaction as db:
            db(sql)
            self._exists = True
            self._old_data.update(self._data)

    def update(self):
        """Update the matching record in the database"""
        if not self._exists:
            raise TracError('%(object_name)s does not exist' % self._meta)
        for key in self._meta['key_fields']:
            if self._data[key] != self._old_data[key]:
                raise TracError('%s cannot be changed' % key)
        
        sdata = {'where':','.join(['%s="%s"' % (k, self._data[k])
                                   for k in self._meta['key_fields']]),
                 'values':','.join(['%s="%s"' % (k, self._data[k]) 
                                    for k in self._meta['non_key_fields']])}
        sdata.update(self._meta)
        sql = """UPDATE %(table_name)s SET %(values)s
                 WHERE %(where)s""" % sdata
        with self._env.db_transaction as db:
            db(sql)
            self._old_data.update(self._data)
    
    @classmethod
    def select(cls, env, db=None, where=None):
        """Query the database to get a set of records back"""
        rows = []
        fields = cls._meta['key_fields']+cls._meta['non_key_fields']
        
        sdata = {'fields':','.join(fields),}
        sdata.update(cls._meta)
        sql = 'SELECT %(fields)s FROM %(table_name)s' % sdata
        wherestr = ''
        if where is not None:
            wherestr = ' WHERE ' + ','.join(['%s="%s"' % (k, v) 
                                             for k, v in where.iteritems()])
        for row in env.db_query(sql+wherestr):
            # we won't know which class we need until called
            model = cls.__new__(cls)
            data = dict([(fields[i], row[i]) for i in range(len(fields))])
            model.__init__(env, data)
            rows.append(model)
        return rows

class Product(ModelBase):
    """The Product table"""
    _meta = {'table_name':'bloodhound_product',
            'object_name':'Product',
            'key_fields':['prefix',],
            'non_key_fields':['name', 'description', 'owner'],
            }
    
    @property
    def resource(self):
        """Allow Product to be treated as a Resource"""
        return Resource('product', self.name)
    
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
        super(Product, self).delete()
        #find and update all resources that should move
        where = {'product_id':self._data['prefix']}
        for prm in ProductResourceMap.select(self._env, where=where):
            prm._data['product_id'] = resources_to
            prm.update()


class ProductResourceMap(ModelBase):
    """Table representing the mapping of resources to their product"""
    _meta = {'table_name':'bloodhound_productresourcemap',
            'object_name':'ProductResourceMapping',
            'key_fields':['id',],
            'non_key_fields':['product_id','resource_type','resource_id',],
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

class MultiProductEnvironmentProvider(Component):
    """Provides the means to create the db tables"""
    
    implements(IEnvironmentSetupParticipant)
    
    SCHEMA = [
        Table('bloodhound_product', key = 'prefix') [
            Column('prefix'),
            Column('name'),
            Column('description'),
            Column('owner'),
            ],
        Table('bloodhound_productresourcemap', key = 'id') [
            Column('id', auto_increment=True),
            Column('product_id'),
            Column('resource_type'),
            Column('resource_id'),
            ]
        ]
    
    def get_version(self):
        """Finds the current version of the bloodhound database schema"""
        rows = self.env.db_query("""
            SELECT value FROM system WHERE name = '%s'
            """ % DB_SYSTEM_KEY)
        return int(rows[0][0]) if rows else -1
    
    # IEnvironmentSetupParticipant methods
    def environment_created(self):
        """Insertion of any default data into the database."""
        self.log.debug("creating environment for %s plugin." % PLUGIN_NAME)
    
    def environment_needs_upgrade(self, db_dummy=None):
        """Detects if the installed db version matches the running system"""
        db_installed_version = self.get_version()
        
        if db_installed_version > DB_VERSION:
            raise TracError('''Current db version (%d) newer than supported by
            this version of the %s (%d).''' % (db_installed_version,
                                               PLUGIN_NAME,
                                               DB_VERSION))
        return db_installed_version < DB_VERSION
    
    def upgrade_environment(self, db_dummy=None):
        """Installs or updates tables to current version"""
        self.log.debug("upgrading existing environment for %s plugin." % 
                       PLUGIN_NAME)
        db_installed_version = self.get_version()
        #cursor = db.cursor()
        with self.env.db_transaction as db:
            if db_installed_version < 0:
                # Initial installation
                db("""
                    INSERT INTO system (name, value) VALUES ('%s','%s')
                    """  % (DB_SYSTEM_KEY, DB_VERSION))
                db("ALTER TABLE ticket ADD COLUMN product TEXT")
                self.log.debug("creating initial db tables for %s plugin." % 
                               PLUGIN_NAME)
                
                db_connector, _ = DatabaseManager(self.env)._get_connector()
                for table in self.SCHEMA:
                    for statement in db_connector.to_sql(table):
                        db(statement)
                db_installed_version = self.get_version()

