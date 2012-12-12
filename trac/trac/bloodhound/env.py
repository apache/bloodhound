
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

from trac.env import Environment
import trac.db.util

from db import BloodhoundIterableCursor

__all__ = ["bloodhound_hooks", "BloodhoundEnvironment", "DEFAULT_PRODUCT"]

DEFAULT_PRODUCT = 'default'

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
