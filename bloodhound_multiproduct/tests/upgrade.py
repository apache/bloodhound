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

from sqlite3 import OperationalError
from contextlib import contextmanager
import os
import shutil
import sys
import tempfile
import uuid
if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from trac.attachment import Attachment, AttachmentAdmin
from trac.core import Component, implements
from trac.db import DatabaseManager
from trac.db.schema import Table, Column
from trac.env import IEnvironmentSetupParticipant
from trac.test import Environment
from trac.ticket import Ticket
from trac.wiki import WikiPage

from multiproduct.api import MultiProductSystem
from multiproduct.env import ProductEnvironment
from multiproduct.model import Product

BLOODHOUND_TABLES = (
    'bloodhound_product',
    'bloodhound_productconfig',
    'bloodhound_productresourcemap',
)

TABLES_WITH_PRODUCT_FIELD = (
    'ticket', 'ticket_change', 'ticket_custom', 'attachment', 'component',
    'milestone', 'wiki', 'report',
    'version', 'enum', 'permission', 'system',
)


class EnvironmentUpgradeTestCase(unittest.TestCase):
    def setUp(self, options=()):
        self.env_path = tempfile.mkdtemp('multiproduct-tempenv')
        self.env = Environment(self.env_path, create=True, options=options)
        DummyPlugin.version = 1

    def tearDown(self):
        shutil.rmtree(self.env_path)

    def test_can_upgrade_environment_with_multi_product_disabled(self):
        self.env.upgrade()

        # Multiproduct was not enabled so multiproduct tables should not exist
        for table in BLOODHOUND_TABLES:
            with self.assertFailsWithMissingTable():
                self.env.db_direct_query("SELECT * FROM %s" % table)

        for table in TABLES_WITH_PRODUCT_FIELD:
            with self.assertFailsWithMissingColumn():
                self.env.db_direct_query("SELECT product FROM %s" % table)

    def test_upgrade_creates_multi_product_tables_and_adds_product_column(self):
        self._enable_multiproduct()
        self.env.upgrade()

        with self.env.db_direct_transaction as db:
            for table in BLOODHOUND_TABLES:
                db("SELECT * FROM %s" % table)

            for table in TABLES_WITH_PRODUCT_FIELD:
                db("SELECT product FROM %s" % table)

    def test_upgrade_creates_default_product(self):
        self._enable_multiproduct()
        self.env.upgrade()

        products = Product.select(self.env)
        self.assertEqual(len(products), 1)

    def test_upgrade_moves_tickets_and_related_objects_to_default_prod(self):
        self._add_custom_field('custom_field')
        with self.env.db_direct_transaction as db:
            db("""INSERT INTO ticket (id) VALUES (1)""")
            db("""INSERT INTO attachment (type, id, filename)
                       VALUES ('ticket', '1', '')""")
            db("""INSERT INTO ticket_custom (ticket, name, value)
                       VALUES (1, 'custom_field', '42')""")
            db("""INSERT INTO ticket_change (ticket, time, field)
                       VALUES (1, 42, 'summary')""")

        self._enable_multiproduct()
        self.env.upgrade()

        with self.product('@'):
            ticket = Ticket(self.env, 1)
            attachments = list(Attachment.select(self.env,
                                                 ticket.resource.realm,
                                                 ticket.resource.id))
            self.assertEqual(len(attachments), 1)
            self.assertEqual(ticket['custom_field'], '42')
            changes = ticket.get_changelog()
            self.assertEqual(len(changes), 3)

    def test_upgrade_moves_custom_wikis_to_default_product(self):
        with self.env.db_direct_transaction as db:
            db("""INSERT INTO wiki (name, version) VALUES ('MyPage', 1)""")
            db("""INSERT INTO attachment (type, id, filename)
                         VALUES ('wiki', 'MyPage', '')""")

        self._enable_multiproduct()
        self.env.upgrade()

        with self.env.db_direct_transaction as db:
            self.assertEqual(
                len(db("""SELECT * FROM wiki WHERE product='@'""")), 1)
            self.assertEqual(
                len(db("""SELECT * FROM attachment
                           WHERE product='@'
                             AND type='wiki'""")), 1)

    def test_upgrade_moves_system_wikis_to_products(self):
        with self.env.db_direct_transaction as db:
            db("""INSERT INTO wiki (name, version) VALUES ('WikiStart', 1)""")
            db("""INSERT INTO attachment (type, id, filename)
                         VALUES ('wiki', 'WikiStart', '')""")

        self._enable_multiproduct()
        self.env.upgrade()

        with self.env.db_direct_transaction as db:
            self.assertEqual(
                len(db("""SELECT * FROM wiki WHERE product='@'""")), 1)
            self.assertEqual(
                len(db("""SELECT * FROM attachment
                           WHERE product='@'
                             AND type='wiki'""")), 1)
            self.assertEqual(
                len(db("""SELECT * FROM wiki WHERE product=''""")), 0)
            self.assertEqual(
                len(db("""SELECT * FROM attachment
                           WHERE product=''
                             AND type='wiki'""")), 0)

    def test_upgrade_copies_content_of_system_tables_to_all_products(self):
        mp = MultiProductSystem(self.env)
        with self.env.db_direct_transaction as db:
            mp._add_column_product_to_ticket(db)
            mp._create_multiproduct_tables(db)
            mp._update_db_version(db, 1)
            for i in range(1, 6):
                db("""INSERT INTO bloodhound_product (prefix, name)
                           VALUES ('p%d', 'Product 1')""" % i)
            for table in ('component', 'milestone', 'enum', 'version',
                          'permission', 'report'):
                db("""DELETE FROM %s""" % table)
            db("""INSERT INTO component (name) VALUES ('foobar')""")
            db("""INSERT INTO milestone (name) VALUES ('foobar')""")
            db("""INSERT INTO version (name) VALUES ('foobar')""")
            db("""INSERT INTO enum (type, name) VALUES ('a', 'b')""")
            db("""INSERT INTO permission VALUES ('x', 'TICKET_VIEW')""")
            db("""INSERT INTO report (title) VALUES ('x')""")

        self._enable_multiproduct()
        self.env.upgrade()

        with self.env.db_direct_transaction as db:
            for table in ('component', 'milestone', 'version', 'enum',
                          'report'):
                rows = db("SELECT * FROM %s" % table)
                self.assertEqual(
                    len(rows), 6,
                    "Wrong number of lines in %s (%d instead of %d)\n%s"
                    % (table, len(rows), 6, rows))
            for table in ('permission',):
                # Permissions also hold rows for global product.
                rows = db("SELECT * FROM %s WHERE username='x'" % table)
                self.assertEqual(
                    len(rows), 7,
                    "Wrong number of lines in %s (%d instead of %d)\n%s"
                    % (table, len(rows), 7, rows))

    def test_upgrading_database_moves_attachment_to_correct_product(self):
        ticket = self.insert_ticket('ticket')
        wiki = self.insert_wiki('MyWiki')
        attachment = self._create_file_with_content('Hello World!')
        self.add_attachment(ticket.resource, attachment)
        self.add_attachment(wiki.resource, attachment)

        self._enable_multiproduct()
        self.env.upgrade()

        with self.product('@'):
            attachments = list(
                Attachment.select(self.env, 'ticket', ticket.id))
            attachments.extend(
                Attachment.select(self.env, 'wiki', wiki.name))
        self.assertEqual(len(attachments), 2)
        for attachment in attachments:
            self.assertEqual(attachment.open().read(), 'Hello World!')

    def test_can_upgrade_database_with_ticket_attachment_with_text_ids(self):
        with self.env.db_direct_transaction as db:
            db("""INSERT INTO attachment (id, type, filename)
                       VALUES ('abc', 'ticket', '')""")

        self._enable_multiproduct()
        self.env.upgrade()

    def test_can_upgrade_database_with_orphaned_attachments(self):
        with self.env.db_direct_transaction as db:
            db("""INSERT INTO attachment (id, type, filename)
                       VALUES ('5', 'ticket', '')""")
            db("""INSERT INTO attachment (id, type, filename)
                       VALUES ('MyWiki', 'wiki', '')""")

        self._enable_multiproduct()
        self.env.upgrade()

    def test_can_upgrade_multi_product_from_v1(self):
        mp = MultiProductSystem(self.env)
        with self.env.db_direct_transaction as db:
            mp._add_column_product_to_ticket(db)
            mp._create_multiproduct_tables(db)
            mp._update_db_version(db, 1)

            db("""INSERT INTO bloodhound_product (prefix, name)
                       VALUES ('p1', 'Product 1')""")
            db("""INSERT INTO ticket (id, product)
                       VALUES (1, 'Product 1')""")

        self._enable_multiproduct()
        self.env.upgrade()

        with self.product('p1'):
            Ticket(self.env, 1)

    def test_can_upgrade_multi_product_from_v2(self):
        mp = MultiProductSystem(self.env)
        with self.env.db_direct_transaction as db:
            mp._add_column_product_to_ticket(db)
            mp._create_multiproduct_tables(db)
            mp._replace_product_on_ticket_with_product_prefix(db)
            mp._update_db_version(db, 2)

            db("""INSERT INTO bloodhound_product (prefix, name)
                       VALUES ('p1', 'Product 1')""")
            db("""INSERT INTO ticket (id, product)
                       VALUES (1, 'p1')""")
            db("""INSERT INTO ticket (id)
                       VALUES (2)""")

        self._enable_multiproduct()
        self.env.upgrade()

        with self.product('p1'):
            Ticket(self.env, 1)
        with self.product('@'):
            Ticket(self.env, 2)

    def test_upgrade_plugin(self):
        self._enable_component(DummyPlugin)
        self.env.upgrade()

        with self.env.db_direct_transaction as db:
            db("SELECT v1 FROM dummy_table")
            with self.assertFailsWithMissingColumn():
                db("SELECT v2 FROM dummy_table")

        DummyPlugin.version = 2
        self.env.upgrade()

        with self.env.db_direct_transaction as db:
            db("SELECT v2 FROM dummy_table")

    def test_upgrade_plugin_to_multiproduct(self):
        self._enable_multiproduct()
        self._enable_component(DummyPlugin)
        self.env.upgrade()

        with self.env.db_direct_transaction as db:
            db("SELECT * FROM dummy_table")
            db("""SELECT * FROM "@_dummy_table" """)

    def test_upgrade_existing_plugin_to_multiproduct(self):
        self._enable_component(DummyPlugin)
        self.env.upgrade()
        with self.env.db_direct_transaction as db:
            with self.assertFailsWithMissingTable():
                db("""SELECT * FROM "@_dummy_table" """)

        self._enable_multiproduct()
        self.env.upgrade()
        with self.env.db_direct_transaction as db:
            db("SELECT * FROM dummy_table")
            db("""SELECT * FROM "@_dummy_table" """)

    def test_upgrading_existing_plugin_leaves_data_in_global_env(self):
        DummyPlugin.version = 2
        self._enable_component(DummyPlugin)
        self.env.upgrade()
        with self.env.db_direct_transaction as db:
            for i in range(5):
                db("INSERT INTO dummy_table (v1) VALUES ('%d')" % i)
            self.assertEqual(
                len(db("SELECT * FROM dummy_table")), 5)

        self._enable_multiproduct()
        self.env.upgrade()
        with self.env.db_direct_transaction as db:
            self.assertEqual(
                len(db('SELECT * FROM "dummy_table"')), 5)
            self.assertEqual(
                len(db('SELECT * FROM "@_dummy_table"')), 0)

    def test_creating_new_product_calls_environment_created(self):
        self._enable_component(DummyPlugin)
        self._enable_multiproduct()
        self.env.upgrade()

        prod = Product(self.env)
        prod.update_field_dict(dict(prefix='p1'))
        ProductEnvironment(self.env, prod, create=True)
        with self.env.db_direct_transaction as db:
            db('SELECT * FROM "p1_dummy_table"')

    def test_migrating_to_multiproduct_with_custom_default_prefix(self):
        ticket = self.insert_ticket('ticket')

        self.env.config.set('multiproduct', 'default_product_prefix', 'xxx')
        self._enable_multiproduct()
        self.env.upgrade()

        products = Product.select(self.env)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].prefix, 'xxx')

    def _enable_multiproduct(self):
        self._update_config('components', 'multiproduct.*', 'enabled')

    def _add_custom_field(self, field_name):
        self._update_config('ticket-custom', field_name, 'text')

    def _enable_component(self, cls):
        self._update_config(
            'components',
            '%s.%s' % (cls.__module__, cls.__name__),
            'enabled'
        )

    def _update_config(self, section, key, value):
        self.env.config.set(section, key, value)
        self.env.config.save()
        self.env = Environment(self.env_path)

    def _create_file_with_content(self, content):
        filename = str(uuid.uuid4())[:6]
        path = os.path.join(self.env_path, filename)
        with open(path, 'wb') as f:
            f.write(content)
        return path

    @contextmanager
    def assertFailsWithMissingTable(self):
        with self.assertRaises(OperationalError) as cm:
            yield
        self.assertIn('no such table', str(cm.exception))

    @contextmanager
    def assertFailsWithMissingColumn(self):
        with self.assertRaises(OperationalError) as cm:
            yield
        self.assertIn('no such column', str(cm.exception))

    def create_ticket(self, summary, **kw):
        ticket = Ticket(self.env)
        ticket["summary"] = summary
        for k, v in kw.items():
            ticket[k] = v
        return ticket

    def insert_ticket(self, summary, **kw):
        """Helper for inserting a ticket into the database"""
        ticket = self.create_ticket(summary, **kw)
        ticket.insert()
        return ticket

    def create_wiki(self, name, text,  **kw):
        page = WikiPage(self.env, name)
        page.text = text
        for k, v in kw.items():
            page[k] = v
        return page

    def insert_wiki(self, name, text = None, **kw):
        text = text or "Dummy text"
        page = self.create_wiki(name, text, **kw)
        page.save("dummy author", "dummy comment", "::1")
        return page

    def add_attachment(self, resource, path):
        resource = '%s:%s' % (resource.realm, resource.id)
        AttachmentAdmin(self.env)._do_add(resource, path)

    @contextmanager
    def product(self, prefix):
        old_env = self.env
        self.env = ProductEnvironment(self.env, prefix)
        yield
        self.env = old_env


class DummyPlugin(Component):
    implements(IEnvironmentSetupParticipant)
    version = 1

    def environment_created(self):
        with self.env.db_transaction as db:
            self.upgrade_environment(db)

    def environment_needs_upgrade(self, db):
        return self.get_version(db) < self.version

    def upgrade_environment(self, db):
        old_version = current_version = self.get_version(db)
        db_connector, dummy = DatabaseManager(self.env)._get_connector()

        while current_version < self.version:
            if current_version > 0:
                db("CREATE TEMPORARY TABLE dummy_table_old AS "
                               "SELECT * FROM dummy_table")
                db("DROP TABLE dummy_table")

            table = self.construct_dummy_table(current_version+1)
            for statement in db_connector.to_sql(table):
                db(statement)

            if current_version > 0:
                cols = ['id'] + ['v%i' % (i+1)
                                 for i in range(current_version+1)]
                db("""INSERT INTO dummy_table (%s)
                                  SELECT %s, '' FROM dummy_table_old
                   """ % (', '.join(cols), ', '.join(cols[:-1])))
                db("DROP TABLE dummy_table_old")

            current_version += 1

        if current_version != old_version:
            self.update_version(db, current_version)

    def construct_dummy_table(self, n_custom_fields=1):
        fields = [Column('id')] + [
            Column('v%d' % (i+1)) for i in range(n_custom_fields)
        ]
        return Table('dummy_table')[fields]

    def get_version(self, db):
        rows = db("SELECT value FROM system WHERE name = %s",
                  (self.__class__.__name__,))
        return int(rows[0][0]) if rows else 0

    def update_version(self, db, version):
        old_version = self.get_version(db)
        if old_version:
            db("UPDATE system SET value=%s WHERE name=%s",
               (version, self.__class__.__name__,))
        else:
            db("INSERT INTO system (name, value) VALUES ('%s','%s')"
               % (self.__class__.__name__, version))
        return version


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(EnvironmentUpgradeTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
