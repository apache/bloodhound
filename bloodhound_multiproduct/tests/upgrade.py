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
import tempfile
import unittest
import uuid

from trac.attachment import Attachment, AttachmentAdmin
from trac.core import Component, implements
from trac.db import DatabaseManager
from trac.db.schema import Table, Column
from trac.env import IEnvironmentSetupParticipant
from trac.test import Environment
from trac.ticket import Ticket
from trac.wiki import WikiPage

from multiproduct.env import ProductEnvironment
from multiproduct.model import Product

BLOODHOUND_TABLES = (
    'bloodhound_product',
    'bloodhound_productconfig',
    'bloodhound_productresourcemap',
)

TABLES_WITH_PRODUCT_FIELD = (
    'component',
    'milestone',
    'version',
    'enum',
    'permission',
    'wiki',
    'report',
)


class EnvironmentUpgradeTestCase(unittest.TestCase):
    def setUp(self):
        self.env_path = tempfile.mkdtemp('multiproduct-tempenv')
        self.env = Environment(self.env_path, create=True)
        self.enabled_components = []
        DummyPlugin.version = 1

    def test_upgrade_environment(self):
        self.env.upgrade()

        with self.env.db_direct_transaction as db:
            for table in BLOODHOUND_TABLES:
                with self.assertFailsWithMissingTable():
                    db("SELECT * FROM %s" % table)

            for table in TABLES_WITH_PRODUCT_FIELD:
                with self.assertFailsWithMissingColumn():
                    db("SELECT product FROM %s" % table)

    def test_upgrade_environment_to_multiproduct(self):
        self._enable_multiproduct()
        self.env.upgrade()

        with self.env.db_direct_transaction as db:
            for table in BLOODHOUND_TABLES:
                db("SELECT * FROM %s" % table)

            for table in TABLES_WITH_PRODUCT_FIELD:
                db("SELECT product FROM %s" % table)

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

    def test_upgrade_moves_tickets_to_default_product(self):
        with self.env.db_direct_transaction as db:
            db("""INSERT INTO ticket (id) VALUES (1)""")
            db("""INSERT INTO attachment (type, id)
                         VALUES ('ticket', '1')""")

        self._enable_multiproduct()
        self.env.upgrade()

        with self.env.db_direct_transaction as db:
            self.assertEqual(
                len(db("""SELECT * FROM ticket WHERE product='@'""")), 1)
            self.assertEqual(
                len(db("""SELECT * FROM attachment
                          WHERE product='@'
                            AND type='ticket'""")), 1)

    def test_upgrade_moves_wikis_to_default_product(self):
        with self.env.db_direct_transaction as db:
            db("""INSERT INTO wiki (name, version) VALUES ('MyPage', 1)""")
            db("""INSERT INTO attachment (type, id)
                         VALUES ('wiki', 'MyPage')""")

        self._enable_multiproduct()
        self.env.upgrade()

        with self.env.db_direct_transaction as db:
            self.assertEqual(
                len(db("""SELECT * FROM wiki WHERE product='@'""")), 1)
            self.assertEqual(
                len(db("""SELECT * FROM attachment
                           WHERE product='@'
                             AND type='wiki'""")), 1)

    def test_upgrade_duplicates_system_wikis_to_products(self):
        with self.env.db_direct_transaction as db:
            db("""INSERT INTO wiki (name, version) VALUES ('WikiStart', 1)""")
            db("""INSERT INTO attachment (type, id)
                         VALUES ('wiki', 'WikiStart')""")

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
                len(db("""SELECT * FROM wiki WHERE product=''""")), 1)
            self.assertEqual(
                len(db("""SELECT * FROM attachment
                           WHERE product=''
                             AND type='wiki'""")), 1)

    def test_can_upgrade_database_with_orphaned_attachments(self):
        with self.env.db_direct_transaction as db:
            db("""INSERT INTO attachment (id, type)
                       VALUES ('5', 'ticket')""")
            db("""INSERT INTO attachment (id, type)
                       VALUES ('MyWiki', 'wiki')""")

        self._enable_multiproduct()
        self.env.upgrade()

    def test_can_upgrade_database_with_text_attachment_ids(self):
        with self.env.db_direct_transaction as db:
            db("""INSERT INTO attachment (id, type)
                       VALUES ('abc', 'ticket')""")

        self._enable_multiproduct()
        self.env.upgrade()

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

    def test_upgrading_database_copies_attachments_for_system_wikis(self):
        wiki = self.insert_wiki('WikiStart', 'content')
        self.add_attachment(wiki.resource,
                            self._create_file_with_content('Hello World!'))

        self._enable_multiproduct()
        self.env.upgrade()

        with self.product('@'):
            attachments = list(
                Attachment.select(self.env, 'wiki', 'WikiStart'))
        attachments.extend(Attachment.select(self.env, 'wiki', 'WikiStart'))
        self.assertEqual(len(attachments), 2)
        for attachment in attachments:
            self.assertEqual(attachment.open().read(), 'Hello World!')

    def _enable_multiproduct(self):
        self.env.config.set('components', 'multiproduct.*', 'enabled')
        self.env.config.save()
        self._reload_environment()
        self._reenable_components()

    def _enable_component(self, cls):
        self.env.config.set('components',
                            '%s.%s' % (cls.__module__, cls.__name__),
                            'enabled')
        self.enabled_components.append(cls)
        self.env.compmgr.enabled[cls] = True

    def _reload_environment(self):
        self.env = Environment(self.env_path)

    def _reenable_components(self):
        for cls in self.enabled_components:
            self.env.compmgr.enabled[cls] = True

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

        if current_version < 1 <= self.version:
            db_connector, dummy = DatabaseManager(self.env)._get_connector()
            for statement in db_connector.to_sql(DUMMY_TABLE):
                db(statement)
            current_version = 1
        while current_version < self.version:
            current_version += 1
            db("ALTER TABLE dummy_table "
               "ADD COLUMN v%d text" % current_version)
        if current_version != old_version:
            self.update_version(db, current_version)

    def get_version(self, db):
        rows = db("SELECT value FROM system WHERE name = %s",
                  (self.__class__.__name__,))
        return int(rows[0][0]) if rows else -1

    def update_version(self, db, version):
        old_version = self.get_version(db)
        if old_version != -1:
            db("UPDATE system SET value=%s WHERE name=%s",
               (version, self.__class__.__name__,))
        else:
            db("INSERT INTO system (name, value) VALUES ('%s','%s')"
               % (self.__class__.__name__, version))
        return version

DUMMY_TABLE = Table('dummy_table')[(
    Column('id'),
    Column('v1'),
)]


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(EnvironmentUpgradeTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
