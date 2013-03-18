
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

from trac.db import Table, Column
from trac.core import TracError
from trac.resource import ResourceNotFound, ResourceSystem
from trac.ticket.api import TicketSystem


def dict_to_kv_str(data=None, sep=' AND '):
    """Converts a dictionary into a string and a list suitable for using as part
    of an SQL where clause like:
        ('key0=%s AND key1=%s', ['value0','value1'])
    The sep argument allows ' AND ' to be changed for ',' for UPDATE purposes
    """
    if data is None:
        return ('', [])
    return (sep.join(['%s=%%s' % k for k in data.keys()]), data.values())

def fields_to_kv_str(fields, data, sep=' AND '):
    """Converts a list of fields and a dictionary containing those fields into a
    string and a list suitable for using as part of an SQL where clause like:
        ('key0=%s,key1=%s', ['value0','value1'])
    """
    return dict_to_kv_str(dict([(f, data[f]) for f in fields]), sep)

class ModelBase(object):
    """Base class for the models to factor out common features
    Derived classes should provide a meta dictionary to describe the table like:
    
    _meta = {'table_name':'mytable',
             'object_name':'WhatIWillCallMyselfInMessages',
             'key_fields':['id','id2'],
             'non_key_fields':['thing','anotherthing'],
             'auto_inc_fields': ['id',],
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
        data = self.__dict__.get('_data')
        fields = self.__dict__.get('_all_fields')
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
        where, values = fields_to_kv_str(self._meta['key_fields'], keys)
        fields = ','.join(self._meta['key_fields']+self._meta['non_key_fields'])
        sdata = {'fields':fields,
                 'where':where}
        sdata.update(self._meta)
        
        sql = """SELECT %(fields)s FROM %(table_name)s
                 WHERE %(where)s""" % sdata
        with self._env.db_query as db:
            for row in db(sql, values):
                self._update_from_row(row)
                break
            else:
                raise ResourceNotFound('No %(object_name)s with %(where)s' %
                                sdata)
    
    def delete(self):
        """Deletes the matching record from the database"""
        if not self._exists:
            raise TracError('%(object_name)s does not exist' % self._meta)
        where, values = fields_to_kv_str(self._meta['key_fields'], self._data)
        sdata = {'where': where}
        sdata.update(self._meta)
        sql = """DELETE FROM %(table_name)s
                 WHERE %(where)s""" % sdata
        with self._env.db_transaction as db:
            db(sql, values)
            self._exists = False
            TicketSystem(self._env).reset_ticket_fields()
        ResourceSystem(self._env).resource_deleted(self)
        self._data = dict([(k, None) for k in self._data.keys()])
        self._old_data.update(self._data)

    
    def insert(self):
        """Create new record in the database"""
        sdata = None
        if self._exists or len(self.select(self._env, where =
                                dict([(k,self._data[k])
                                      for k in self._meta['key_fields']]))):
            sdata = {'keys':','.join(["%s='%s'" % (k, self._data[k])
                                     for k in self._meta['key_fields']])}
        elif self._meta['unique_fields'] and len(self.select(self._env, where = 
                                dict([(k,self._data[k])
                                      for k in self._meta['unique_fields']]))):
            sdata = {'keys':','.join(["%s='%s'" % (k, self._data[k])
                                     for k in self._meta['unique_fields']])}
        if sdata:
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
                 'values':','.join(['%s'] * len(fields))}
        sdata.update(self._meta)
        
        sql = """INSERT INTO %(table_name)s (%(fields)s)
                 VALUES (%(values)s)""" % sdata
        with self._env.db_transaction as db:
            db(sql, [self._data[f] for f in fields])
            self._exists = True
            self._old_data.update(self._data)
            TicketSystem(self._env).reset_ticket_fields()
        ResourceSystem(self._env).resource_created(self)

    def _update_relations(self, db):
        """Extra actions due to update"""
        pass
    
    def update(self):
        """Update the matching record in the database"""
        if self._old_data == self._data:
            return 
        if not self._exists:
            raise TracError('%(object_name)s does not exist' % self._meta)
        for key in self._meta['no_change_fields']:
            if self._data[key] != self._old_data[key]:
                raise TracError('%s cannot be changed' % key)
        for key in self._meta['key_fields'] + self._meta['unique_fields']:
            if self._data[key] != self._old_data[key]:
                if len(self.select(self._env, where = {key:self._data[key]})):
                    raise TracError('%s already exists' % key)
        
        setsql, setvalues = fields_to_kv_str(self._meta['non_key_fields'],
                                             self._data, sep=',')
        where, values = fields_to_kv_str(self._meta['key_fields'], self._data)
        
        sdata = {'where': where,
                 'values': setsql}
        sdata.update(self._meta)
        sql = """UPDATE %(table_name)s SET %(values)s
                 WHERE %(where)s""" % sdata

        old_values = dict((k, v) for k, v in self._old_data.iteritems()
                          if self._data.get(k) != v)
        with self._env.db_transaction as db:
            db(sql, setvalues + values)
            self._update_relations(db)
            self._old_data.update(self._data)
            TicketSystem(self._env).reset_ticket_fields()

        ResourceSystem(self._env).resource_changed(self, old_values)

    
    @classmethod
    def select(cls, env, db=None, where=None):
        """Query the database to get a set of records back"""
        rows = []
        fields = cls._meta['key_fields']+cls._meta['non_key_fields']
        
        sdata = {'fields':','.join(fields),}
        sdata.update(cls._meta)
        sql = r'SELECT %(fields)s FROM %(table_name)s' % sdata
        wherestr, values = dict_to_kv_str(where)
        if wherestr:
            wherestr = ' WHERE ' + wherestr
        for row in env.db_query(sql + wherestr, values):
            # we won't know which class we need until called
            model = cls.__new__(cls)
            data = dict([(fields[i], row[i]) for i in range(len(fields))])
            model.__init__(env, data)
            rows.append(model)
        return rows
    
    @classmethod
    def _get_fields(cls):
        return cls._meta['key_fields']+cls._meta['non_key_fields']
    
    @classmethod
    def _get_schema(cls):
        """Generate schema from the class meta data"""
        auto_inc =  cls._meta.get('auto_inc_fields', [])
        fields =  [Column(f, auto_increment=f in auto_inc)
                   for f in cls._get_fields()]
        return Table(cls._meta['table_name'], key=set(cls._meta['key_fields'] +
                            cls._meta['unique_fields'])) [fields]

