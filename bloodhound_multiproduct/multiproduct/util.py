
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

"""Bloodhound multiproduct utility APIs"""

from trac import db_default
from multiproduct.api import MultiProductSystem

import collections
import functools

class ProductDelegate(object):
    @staticmethod
    def add_product(env, product, keys, field_data):
        product.update_field_dict(keys)
        product.update_field_dict(field_data)
        product.insert()

        env.log.debug("Adding product info (%s) to tables:" % product.prefix)
        with env.db_direct_transaction as db:
            # create the default entries for this Product from defaults
            for table in db_default.get_data(db):
                if not table[0] in MultiProductSystem.MIGRATE_TABLES:
                    continue

                env.log.debug("  -> %s" % table[0])
                cols = table[1] + ('product', )
                rows = [p + (product.prefix, ) for p in table[2]]
                db.executemany(
                    "INSERT INTO %s (%s) VALUES (%s)" %
                    (table[0], ','.join(cols), ','.join(['%s' for c in cols])),
                    rows)

            # in addition copy global admin permissions (they are
            # not part of the default permission table)
            rows = db("""SELECT username FROM permission WHERE action='TRAC_ADMIN'
                         AND product=''""")
            rows = [(r[0], 'TRAC_ADMIN', product.prefix) for r in rows]
            cols = ('username', 'action', 'product')
            db.executemany("INSERT INTO permission (%s) VALUES (%s)" %
                (','.join(cols), ','.join(['%s' for c in cols])), rows)

def lru_cache(maxsize=100):
    """Simple LRU cache decorator, using `collections.OrderedDict` for
    item store
    """
    def wrap(f):
        cache = collections.OrderedDict()
        @functools.wraps(f)
        def wrapped_func(*args, **kwargs):
            key = args
            if kwargs:
                key += tuple(sorted(kwargs.items()))
            try:
                item = cache.pop(key)
            except KeyError:
                item = f(*args, **kwargs)
                if len(cache) >= maxsize:
                    cache.popitem(last=False)
            cache[key] = item
            return item
        return wrapped_func
    return wrap
