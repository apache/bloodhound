
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

def dict_to_kv_str(env, data=None, sep=' AND '):
    """Converts a dictionary into a string and a list suitable for using as part
    of an SQL where clause like:
        ('key0=%s AND key1=%s', ['value0','value1'])
    The sep argument allows ' AND ' to be changed for ',' for UPDATE purposes
    """
    if data is None:
        return ('', [])
    qfn = env.get_read_db().quote
    return (sep.join('%s=%%s' % qfn(k) for k in data.keys()),
            data.values())

def fields_to_kv_str(env, fields, data, sep=' AND '):
    """Converts a list of fields and a dictionary containing those fields into a
    string and a list suitable for using as part of an SQL where clause like:
        ('key0=%s,key1=%s', ['value0','value1'])
    """
    return dict_to_kv_str(env, dict((f, data[f]) for f in fields),sep)

class ModelBase(object):
    """Base class for the models to factor out common features
    Derived classes should provide a meta dictionary to describe the table like:
    
    _meta = {'table_name':'mytable',
             'object_name':'WhatIWillCallMyselfInMessages',
             'key_fields':['id','id2'],
             'non_key_fields':[
                'thing',
                {
                    name:"field_name_x",
                    type='int64',
                    size=None,
                    key_size=None,
                    auto_increment=False
                }],
             'auto_inc_fields': ['id',],
             }
    key_fields and non_key_fields parameters may contain field name only (for
    text columns) or dict with detailed column specification. In case of
    detailed column specification 'name' parameter is obligatory).
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
        self._key_fields = self._get_field_names(self._meta['key_fields'])
        self._non_key_fields = self._get_field_names(
            self._meta['non_key_fields'])
        self._all_fields = self._key_fields + self._non_key_fields
        self._unique_fields = self._meta['unique_fields']
        self._auto_inc_fields = self._get_auto_inc_field_names()

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

    @classmethod
    def get_table_name(cls):
        return cls._meta["table_name"]
    
    def _update_from_row(self, row = None):
        """uses a provided database row to update the model"""
        fields = self._all_fields
        self._exists = row is not None
        if row is None:
            row = [None]*len(fields)
        self._data = dict([(fields[i], row[i]) for i in range(len(row))])
        self._old_data = {}
        self._old_data.update(self._data)
    
    def _get_row(self, keys):
        """queries the database and stores the result in the model"""
        row = None
        where, values = fields_to_kv_str(self._env, self._key_fields, keys)
        fields = ','.join(self._all_fields)
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
                raise ResourceNotFound(
                        ('No %(object_name)s with %(where)s' % sdata) 
                                % tuple(values))
    
    def delete(self):
        """Deletes the matching record from the database"""
        if not self._exists:
            raise TracError('%(object_name)s does not exist' % self._meta)
        where, values = fields_to_kv_str(self._env, self._key_fields,
                                         self._data)
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
                                      for k in self._key_fields]))):
            sdata = {'keys':','.join(["%s='%s'" % (k, self._data[k])
                                     for k in self._key_fields])}
        elif self._unique_fields and len(self.select(self._env, where =
                                dict([(k,self._data[k])
                                      for k in self._unique_fields]))):
            sdata = {'keys':','.join(["%s='%s'" % (k, self._data[k])
                                     for k in self._unique_fields])}
        if sdata:
            sdata.update(self._meta)
            sdata['values'] = self._data
            raise TracError('%(object_name)s %(keys)s already exists %(values)s' %
                            sdata)
            
        for key in self._key_fields:
            if self._data[key] is None and key not in self._auto_inc_fields:
                sdata = {'key':key}
                sdata.update(self._meta)
                raise TracError('%(key)s required for %(object_name)s' %
                                sdata)

        fields = [field for field in self._all_fields
                  if field not in self._auto_inc_fields]
        sdata = {'fields':','.join(fields),
                 'values':','.join(['%s'] * len(fields))}
        sdata.update(self._meta)

        sql = """INSERT INTO %(table_name)s (%(fields)s)
                 VALUES (%(values)s)""" % sdata
        with self._env.db_transaction as db:
            cursor = db.cursor()
            cursor.execute(sql, [self._data[f] for f in fields])
            for auto_in_field in self._auto_inc_fields:
                self._data[auto_in_field] = db.get_last_id(
                    cursor, sdata["table_name"], auto_in_field)

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
        for key in self._key_fields + self._unique_fields:
            if self._data[key] != self._old_data[key]:
                if len(self.select(self._env, where = {key:self._data[key]})):
                    raise TracError('%s already exists' % key)

        setsql, setvalues = fields_to_kv_str(self._env, self._non_key_fields,
                                             self._data, sep=',')
        where, values = fields_to_kv_str(self._env, self._key_fields,
                                         self._data)

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
    def select(cls, env, db=None, where=None, limit=None, order_by=None):
        """
        Query the database to get a set of records back
        * order_by: is list of fields with optional sort direction
            ("asc" or "desc") e.g. ["field1", "field2 desc"]
        """
        rows = []
        fields = cls._get_all_field_names()

        sdata = {'fields': ','.join(env.get_read_db().quote(f)
                                    for f in fields),}
        sdata.update(cls._meta)
        sql = r'SELECT %(fields)s FROM %(table_name)s' % sdata
        wherestr, values = dict_to_kv_str(env, where)
        if wherestr:
            wherestr = ' WHERE ' + wherestr
        final_sql = sql + wherestr
        if limit is not None:
            final_sql += ' LIMIT ' + str(int(limit))
        if order_by:
            final_sql += "\nORDER BY " + ', '.join(order_by)
        for row in env.db_query(final_sql, values):
            # we won't know which class we need until called
            model = cls.__new__(cls)
            data = dict([(fields[i], row[i]) for i in range(len(fields))])
            model.__init__(env, data)
            rows.append(model)
        return rows

    @classmethod
    def _get_all_field_names(cls):
        return cls._get_field_names(
            cls._meta['key_fields']+cls._meta['non_key_fields'])

    @classmethod
    def _get_field_names(cls, field_specs):
        def get_field_name(field_spec):
            if isinstance(field_spec, dict):
                return field_spec["name"]
            return field_spec
        return [get_field_name(field_spec) for field_spec in field_specs]

    @classmethod
    def _get_all_field_columns(cls):
        auto_inc =  cls._meta.get('auto_inc_fields', [])
        columns = []
        all_fields_spec = cls._meta['key_fields'] + cls._meta['non_key_fields']
        for field_spec in all_fields_spec:
            #field_spec can be field name string or dictionary with detailed
            #column specification
            if isinstance(field_spec, dict):
                column_spec = field_spec
            else:
                column_spec = dict(
                    name = field_spec,
                    auto_increment=field_spec in auto_inc)
            columns.append(column_spec)
        return columns

    @classmethod
    def _get_auto_inc_field_names(cls):
        return [field_spec["name"] for field_spec
                in cls._get_all_field_columns()
                if field_spec.get("auto_increment")]

    @classmethod
    def _get_schema(cls):
        """Generate schema from the class meta data"""
        fields =  [Column(
                    column_spec["name"],
                    type=column_spec.get("type", "text"),
                    size=column_spec.get("size"),
                    key_size=column_spec.get("key_size"),
                    auto_increment=column_spec.get("auto_increment", False))
                   for column_spec in cls._get_all_field_columns()]
        return Table(cls._meta['table_name'], key=set(cls._meta['key_fields'] +
                            cls._meta['unique_fields'])) [fields]
