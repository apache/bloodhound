
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

"""Tests for Apache(TM) Bloodhound's ticket queries in product environments"""

import unittest

from trac.ticket.query import Query
from trac.ticket.tests.query import QueryTestCase, QueryLinksTestCase

from multiproduct.env import ProductEnvironment
from tests.env import MultiproductTestCase

class ProductQueryTestCase(QueryTestCase, MultiproductTestCase):

    @property
    def env(self):
        env = getattr(self, '_env', None)
        if env is None:
            self.global_env = self._setup_test_env()
            self._upgrade_mp(self.global_env)
            self._setup_test_log(self.global_env)
            self._load_product_from_data(self.global_env, self.default_product)
            self._env = env = ProductEnvironment(
                    self.global_env, self.default_product)
            self._load_default_data(env)
        return env

    @env.setter
    def env(self, value):
        pass

    def tearDown(self):
        self.global_env.reset_db()
        self.global_env = self._env = None

    def test_all_grouped_by_milestone(self):
        query = Query(self.env, order='id', group='milestone')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
  LEFT OUTER JOIN milestone ON (milestone.name=milestone)
ORDER BY COALESCE(t.milestone,'')='',COALESCE(milestone.completed,0)=0,milestone.completed,COALESCE(milestone.due,0)=0,milestone.due,t.milestone,COALESCE(t.id,0)=0,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(self.req)

    def test_all_grouped_by_milestone_desc(self):
        query = Query(self.env, order='id', group='milestone', groupdesc=1)
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
  LEFT OUTER JOIN milestone ON (milestone.name=milestone)
ORDER BY COALESCE(t.milestone,'')='' DESC,COALESCE(milestone.completed,0)=0 DESC,milestone.completed DESC,COALESCE(milestone.due,0)=0 DESC,milestone.due DESC,t.milestone DESC,COALESCE(t.id,0)=0,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(self.req)

    def test_all_ordered_by_id(self):
        query = Query(self.env, order='id')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(self.req)

    def test_all_ordered_by_id_desc(self):
        query = Query(self.env, order='id', desc=1)
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(t.id,0)=0 DESC,t.id DESC""")
        self.assertEqual([], args)
        tickets = query.execute(self.req)

    def test_all_ordered_by_id_from_unicode(self):
        query = Query.from_string(self.env, u'order=id')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(self.req)

    def test_all_ordered_by_id_verbose(self):
        query = Query(self.env, order='id', verbose=1)
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.reporter AS reporter,t.description AS description,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(self.req)

    def test_all_ordered_by_priority(self):
        query = Query(self.env) # priority is default order
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(priority.value,'')='',%(cast_priority)s,t.id""" % {
          'cast_priority': self.env.get_read_db().cast('priority.value', 'int')})
        self.assertEqual([], args)
        tickets = query.execute(self.req)

    def test_all_ordered_by_priority_desc(self):
        query = Query(self.env, desc=1) # priority is default order
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(priority.value,'')='' DESC,%(cast_priority)s DESC,t.id""" % {
          'cast_priority': self.env.get_read_db().cast('priority.value', 'int')})
        self.assertEqual([], args)
        tickets = query.execute(self.req)

    def test_constrained_by_custom_field(self):
        self.env.config.set('ticket-custom', 'foo', 'text')
        query = Query.from_string(self.env, 'foo=something', order='id')
        sql, args = query.get_sql()
        foo = self.env.get_read_db().quote('foo')
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value,%s.value AS %s
FROM ticket AS t
  LEFT OUTER JOIN ticket_custom AS %s ON (id=%s.ticket AND %s.name='foo')
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE ((COALESCE(%s.value,'')=%%s))
ORDER BY COALESCE(t.id,0)=0,t.id""" % ((foo,) * 6))
        self.assertEqual(['something'], args)
        tickets = query.execute(self.req)

    def test_constrained_by_empty_value_contains(self):
        query = Query.from_string(self.env, 'owner~=|', order='id')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(self.req)

    def test_constrained_by_empty_value_endswith(self):
        query = Query.from_string(self.env, 'owner$=|', order='id')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(self.req)

    def test_constrained_by_empty_value_startswith(self):
        query = Query.from_string(self.env, 'owner^=|', order='id')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(self.req)

    def test_constrained_by_milestone(self):
        query = Query.from_string(self.env, 'milestone=milestone1', order='id')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,t.milestone AS milestone,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE ((COALESCE(t.milestone,'')=%s))
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['milestone1'], args)
        tickets = query.execute(self.req)

    def test_constrained_by_milestone_or_version(self):
        query = Query.from_string(self.env, 'milestone=milestone1&or&version=version1', order='id')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,t.version AS version,t.milestone AS milestone,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE ((COALESCE(t.milestone,'')=%s)) OR ((COALESCE(t.version,'')=%s))
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['milestone1', 'version1'], args)
        tickets = query.execute(self.req)

    def test_constrained_by_multiple_owners(self):
        query = Query.from_string(self.env, 'owner=someone|someone_else',
                                  order='id')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE (COALESCE(t.owner,'') IN (%s,%s))
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['someone', 'someone_else'], args)
        tickets = query.execute(self.req)

    def test_constrained_by_multiple_owners_contain(self):
        query = Query.from_string(self.env, 'owner~=someone|someone_else',
                                  order='id')
        sql, args = query.get_sql()
        self.assertEqual(['%someone%', '%someone/_else%'], args)
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE ((COALESCE(t.owner,'') %(like)s OR COALESCE(t.owner,'') %(like)s))
ORDER BY COALESCE(t.id,0)=0,t.id""" % {'like': self.env.get_read_db().like()})
        tickets = query.execute(self.req)

    def test_constrained_by_multiple_owners_not(self):
        query = Query.from_string(self.env, 'owner!=someone|someone_else',
                                  order='id')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE (COALESCE(t.owner,'') NOT IN (%s,%s))
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['someone', 'someone_else'], args)
        tickets = query.execute(self.req)

    def test_constrained_by_owner_beginswith(self):
        query = Query.from_string(self.env, 'owner^=someone', order='id')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE ((COALESCE(t.owner,'') %(like)s))
ORDER BY COALESCE(t.id,0)=0,t.id""" % {'like': self.env.get_read_db().like()})
        self.assertEqual(['someone%'], args)
        tickets = query.execute(self.req)

    def test_constrained_by_owner_containing(self):
        query = Query.from_string(self.env, 'owner~=someone', order='id')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE ((COALESCE(t.owner,'') %(like)s))
ORDER BY COALESCE(t.id,0)=0,t.id""" % {'like': self.env.get_read_db().like()})
        self.assertEqual(['%someone%'], args)
        tickets = query.execute(self.req)

    def test_constrained_by_owner_endswith(self):
        query = Query.from_string(self.env, 'owner$=someone', order='id')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE ((COALESCE(t.owner,'') %(like)s))
ORDER BY COALESCE(t.id,0)=0,t.id""" % {'like': self.env.get_read_db().like()})
        self.assertEqual(['%someone'], args)
        tickets = query.execute(self.req)

    def test_constrained_by_owner_not_containing(self):
        query = Query.from_string(self.env, 'owner!~=someone', order='id')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE ((COALESCE(t.owner,'') NOT %(like)s))
ORDER BY COALESCE(t.id,0)=0,t.id""" % {'like': self.env.get_read_db().like()})
        self.assertEqual(['%someone%'], args)
        tickets = query.execute(self.req)

    def test_constrained_by_status(self):
        query = Query.from_string(self.env, 'status=new|assigned|reopened',
                                  order='id')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.status AS status,t.owner AS owner,t.type AS type,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE (COALESCE(t.status,'') IN (%s,%s,%s))
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['new', 'assigned', 'reopened'], args)
        tickets = query.execute(self.req)

    def test_equal_in_value(self):
        query = Query.from_string(self.env, r'status=this=that&version=version1',
                                  order='id')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.priority AS priority,t.product AS product,t.milestone AS milestone,t.status AS status,t.time AS time,t.changetime AS changetime,t.version AS version,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE ((COALESCE(t.status,'')=%s) AND (COALESCE(t.version,'')=%s))
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['this=that', 'version1'], args)
        tickets = query.execute(self.req)

    def test_grouped_by_custom_field(self):
        self.env.config.set('ticket-custom', 'foo', 'text')
        query = Query(self.env, group='foo', order='id')
        sql, args = query.get_sql()
        foo = self.env.get_read_db().quote('foo')
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value,%s.value AS %s
FROM ticket AS t
  LEFT OUTER JOIN ticket_custom AS %s ON (id=%s.ticket AND %s.name='foo')
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(%s.value,'')='',%s.value,COALESCE(t.id,0)=0,t.id""" %
        ((foo,) * 7))
        self.assertEqual([], args)
        tickets = query.execute(self.req)

    def test_grouped_by_priority(self):
        query = Query(self.env, group='priority')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.product AS product,t.milestone AS milestone,t.priority AS priority,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(priority.value,'')='',%(cast_priority)s,t.id""" % {
          'cast_priority': self.env.get_read_db().cast('priority.value', 'int')})
        self.assertEqual([], args)
        tickets = query.execute(self.req)

    def test_special_character_escape(self):
        query = Query.from_string(self.env, r'status=here\&now|maybe\|later|back\slash',
                                  order='id')
        sql, args = query.get_sql()
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.status AS status,t.owner AS owner,t.type AS type,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE (COALESCE(t.status,'') IN (%s,%s,%s))
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['here&now', 'maybe|later', 'back\\slash'], args)
        tickets = query.execute(self.req)

    def test_user_var(self):
        query = Query.from_string(self.env, 'owner=$USER&order=id')
        sql, args = query.get_sql(req=self.req)
        self.assertEqualSQL(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.product AS product,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE ((COALESCE(t.owner,'')=%s))
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['anonymous'], args)
        tickets = query.execute(self.req)


class ProductQueryLinksTestCase(QueryLinksTestCase, MultiproductTestCase):

    @property
    def env(self):
        env = getattr(self, '_env', None)
        if env is None:
            self.global_env = self._setup_test_env()
            self._upgrade_mp(self.global_env)
            self._setup_test_log(self.global_env)
            self._load_product_from_data(self.global_env, self.default_product)
            self._env = env = ProductEnvironment(
                    self.global_env, self.default_product)
            self._load_default_data(env)
        return env

    @env.setter
    def env(self, value):
        pass

    def tearDown(self):
        self.global_env.reset_db()
        self.global_env = self._env = None


def test_suite():
    return unittest.TestSuite([
            unittest.makeSuite(ProductQueryTestCase,'test'),
            unittest.makeSuite(ProductQueryLinksTestCase,'test'),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

