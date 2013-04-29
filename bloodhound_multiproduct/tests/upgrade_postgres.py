# -*- coding: utf-8 -*-
#
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
try:
    import psycopg2
    import uuid
    conn = psycopg2.connect(host='localhost', database='test')
    cur = conn.cursor()
    schema = str(uuid.uuid4()).replace('-', '')
    cur.execute('CREATE SCHEMA "%s"' % schema)
    cur.execute('DROP SCHEMA "%s"' % schema)
    conn.close()
    database_available = True
except Exception as err:
    print err
    database_available = False

from contextlib import contextmanager
import sys
if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import upgrade

@unittest.skipUnless(database_available, "Postgres database not available.")
class PostgresEnvironmentUpgradeTestCase(upgrade.EnvironmentUpgradeTestCase):
    def setUp(self):
        self.schema = str(uuid.uuid4()).replace('-', '')
        super(PostgresEnvironmentUpgradeTestCase, self).setUp(
            (('trac', 'database',
              'postgres://localhost/test?schema=%s' % self.schema),)
        )

    def tearDown(self):
        super(PostgresEnvironmentUpgradeTestCase, self).tearDown()
        conn = psycopg2.connect(host='localhost', database='test')
        cur = conn.cursor()
        cur.execute('DROP SCHEMA "%s" CASCADE' % self.schema)
        conn.commit()
        conn.close()

    @contextmanager
    def assertFailsWithMissingTable(self):
        with self.assertRaises(psycopg2.ProgrammingError) as cm:
            yield
        self.assertIn("relation", str(cm.exception))
        self.assertIn("does not exist", str(cm.exception))

    @contextmanager
    def assertFailsWithMissingColumn(self):
        with self.assertRaises(psycopg2.ProgrammingError) as cm:
            yield
        self.assertIn("column", str(cm.exception))
        self.assertIn("does not exist", str(cm.exception))
