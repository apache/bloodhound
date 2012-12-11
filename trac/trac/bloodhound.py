
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

import trac.env
from trac.db.util import IterableCursor
from trac.util import concurrency
from trac.env import Environment
from bloodhoundsql import BloodhoundProductSQLTranslate

DEFAULT_PRODUCT = 'default'
TRANSLATE_TABLES = ['ticket', 'enum', 'component', 'milestone', 'version', 'wiki']
PRODUCT_COLUMN = 'product'

class BloodhoundIterableCursor(IterableCursor):
    __slots__ = IterableCursor.__slots__ + ['_translator']
    _tls = concurrency.ThreadLocal(env=None)

    def __init__(self, cursor, log=None):
        super(BloodhoundIterableCursor, self).__init__(cursor, log=log)
        self._translator = None

    @property
    def translator(self):
        if not self._translator:
            product = self.env.product_scope if self.env else DEFAULT_PRODUCT
            self._translator = BloodhoundProductSQLTranslate(TRANSLATE_TABLES,
                                                             PRODUCT_COLUMN,
                                                             product)
        return self._translator

    def _translate_sql(self, sql):
        return self.translator.translate(sql) if (self.env and not self.env.product_aware) else sql

    def execute(self, sql, args=None):
        return super(BloodhoundIterableCursor, self).execute(self._translate_sql(sql), args=args)

    def executemany(self, sql, args=None):
        return super(BloodhoundIterableCursor, self).executemany(self._translate_sql(sql), args=args)

    @property
    def env(self):
        return self._tls.env

    @classmethod
    def set_env(cls, env):
        cls._tls.env = env

class BloodhoundEnvironment(Environment):
    def __init__(self, path, create=False, options=[]):
        super(BloodhoundEnvironment, self).__init__(path, create=create, options=options)
        self._product_scope = DEFAULT_PRODUCT
        self._product_aware = False

    @property
    def product_scope(self):
        return self._product_scope
    @product_scope.setter
    def product_scope(self, value):
        self._product_scope = value

    @property
    def product_aware(self):
        return self._product_aware
    @product_aware.setter
    def product_aware(self, value):
        self._product_aware = value

    @property
    def db_query(self):
        BloodhoundIterableCursor.set_env(self)
        return super(BloodhoundEnvironment, self).db_query

    @property
    def db_transaction(self):
        BloodhoundIterableCursor.set_env(self)
        return super(BloodhoundEnvironment, self).db_transaction

def bloodhound_hooks():
    trac.env.Environment = BloodhoundEnvironment
    trac.db.util.IterableCursor = BloodhoundIterableCursor
