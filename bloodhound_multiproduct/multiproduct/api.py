
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

"""Core components to support multi-product"""
from datetime import datetime

from genshi.builder import tag

from pkg_resources import resource_filename
from trac.config import PathOption
from trac.core import Component, TracError, implements
from trac.db import Table, Column, DatabaseManager, Index
from trac.env import IEnvironmentSetupParticipant
from trac.perm import IPermissionRequestor
from trac.resource import IResourceManager
from trac.ticket.api import ITicketFieldProvider
from trac.util.translation import _, N_
from trac.web.chrome import ITemplateProvider

from multiproduct.model import Product, ProductResourceMap, ProductSetting

DB_VERSION = 4
DB_SYSTEM_KEY = 'bloodhound_multi_product_version'
PLUGIN_NAME = 'Bloodhound multi product'

class MultiProductSystem(Component):
    """Creates the database tables and template directories"""

    implements(IEnvironmentSetupParticipant, ITemplateProvider,
            IPermissionRequestor, ITicketFieldProvider, IResourceManager)

    product_config_parent = PathOption('inherit', 'multiproduct', '',
        """The path to the configuration file containing the settings shared
        by sibling product environments. By default will inherit 
        global environment configuration.
        """)

    SCHEMA = [mcls._get_schema() \
              for mcls in (Product, ProductResourceMap)]

    def get_version(self):
        """Finds the current version of the bloodhound database schema"""
        rows = self.env.db_query("""
            SELECT value FROM system WHERE name = %s
            """, (DB_SYSTEM_KEY,))
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

    def _update_db_version(self, db, version):
        old_version = self.get_version()
        if old_version != -1:
            self.log.info("Updating multiproduct database schema from version %d"
                          " to %d" % (old_version, version))
            db("""UPDATE system SET value=%s
                      WHERE name=%s""", (version, DB_SYSTEM_KEY))
        else:
            self.log.info("Initial multiproduct database schema set to version %d" % version)
            db("""
                INSERT INTO system (name, value) VALUES ('%s','%s')
                """  % (DB_SYSTEM_KEY, version))
        return version

    def upgrade_environment(self, db_dummy=None):
        """Installs or updates tables to current version"""
        self.log.debug("upgrading existing environment for %s plugin." % 
                       PLUGIN_NAME)
        db_installed_version = self.get_version()
        with self.env.db_transaction as db:
            if db_installed_version < 1:
                # Initial installation
                db("ALTER TABLE ticket ADD COLUMN product TEXT")
                self.log.debug("creating initial db tables for %s plugin." % 
                               PLUGIN_NAME)
                db_connector, dummy = DatabaseManager(self.env)._get_connector()
                for table in self.SCHEMA:
                    for statement in db_connector.to_sql(table):
                        db(statement)
                db_installed_version = self._update_db_version(db, 1)

            if db_installed_version < 2:
                from multiproduct.model import Product
                products = Product.select(self.env)
                for prod in products:
                    db("""UPDATE ticket SET product=%s
                          WHERE product=%s""", (prod.prefix, prod.name))
                db_installed_version = self._update_db_version(db, 2)

            if db_installed_version < 3:
                from multiproduct.dbcursor import DEFAULT_PRODUCT
                migrate_tables = ['enum', 'component', 'milestone', 'version', 'permission', 'wiki']
                table_defs = [
                    Table('enum', key=('type', 'name', 'product'))[
                        Column('type'),
                        Column('name'),
                        Column('value'),
                        Column('product')],
                    Table('component', key=('name', 'product'))[
                        Column('name'),
                        Column('owner'),
                        Column('description'),
                        Column('product')],
                    Table('milestone', key=('name', 'product'))[
                        Column('name'),
                        Column('due', type='int64'),
                        Column('completed', type='int64'),
                        Column('description'),
                        Column('product')],
                    Table('version', key=('name', 'product'))[
                        Column('name'),
                        Column('time', type='int64'),
                        Column('description'),
                        Column('product')],
                    Table('permission', key=('username', 'action', 'product'))[
                        Column('username'),
                        Column('action'),
                        Column('product')],
                    Table('wiki', key=('name', 'version', 'product'))[
                        Column('name'),
                        Column('version', type='int'),
                        Column('time', type='int64'),
                        Column('author'),
                        Column('ipnr'),
                        Column('text'),
                        Column('comment'),
                        Column('readonly', type='int'),
                        Column('product'),
                        Index(['time'])],
                    ]
                table_columns = dict()
                table_vals = {}
                for table in table_defs:
                    table_columns[table.name] = filter(lambda column: column != 'product',
                                                         [column.name for column in
                                                            list(filter(lambda t: t.name == table.name,
                                                                                  table_defs)[0].columns)])
                table_columns['bloodhound_product'] = ['prefix', 'name', 'description', 'owner']
                def fetch_table(table):
                    table_vals[table] = list(db("SELECT %s FROM %s" % (','.join(table_columns[table]), table)))
                for table in table_columns.keys():
                    self.log.info("Fetching table '%s'", table)
                    fetch_table(table)
                for table in migrate_tables:
                    self.log.info("Dropping obsolete table '%s'", table)
                    db("DROP TABLE %s" % table)
                db_connector, _ = DatabaseManager(self.env).get_connector()
                for table in table_defs:
                    self.log.info("Creating table '%s'", table.name)
                    for sql in db_connector.to_sql(table):
                        db(sql)
                self.log.info("Creating default product")
                db("""INSERT INTO bloodhound_product (prefix, name, description, owner)
                        VALUES ('%s', 'Default', 'Default product', '')""" % DEFAULT_PRODUCT)
                self.log.info("Migrating tickets w/o product to default product")
                db("""UPDATE ticket SET product='%s'
                        WHERE product=''""" % DEFAULT_PRODUCT)

                def insert_with_product(table, product):
                    cols = table_columns[table] + ['product']
                    sql = "INSERT INTO %s (%s) VALUES (%s)" % (table,
                                                               ','.join(cols),
                                                               ','.join(['%s'] * len(cols)))
                    for r in table_vals[table]:
                        vals = list()
                        for v in list(r):
                            vals.append(v if v else '')
                        db(sql, tuple(vals + [product]))
                for table in migrate_tables:
                    self.log.info("Creating tables '%s' for default product", table)
                    insert_with_product(table, DEFAULT_PRODUCT)
                    for p in table_vals['bloodhound_product']:
                        self.log.info("Creating tables '%s' for product '%s' ('%s')", table, p[1], p[0])
                        insert_with_product(table, p[0])
                db_installed_version = self._update_db_version(db, 3)

            if db_installed_version < 4:
                self.log.debug("creating additional db tables for %s plugin." %
                               PLUGIN_NAME)
                db_connector, dummy = DatabaseManager(self.env)._get_connector()
                for statement in db_connector.to_sql(ProductSetting._get_schema()):
                    db(statement)
                db_installed_version = self._update_db_version(db, 4)

    # ITemplateProvider methods
    def get_templates_dirs(self):
        """provide the plugin templates"""
        return [resource_filename(__name__, 'templates')]

    def get_htdocs_dirs(self):
        """proved the plugin htdocs"""
        return []

    # IPermissionRequestor methods
    def get_permission_actions(self):
        acts = ['PRODUCT_CREATE', 'PRODUCT_DELETE', 'PRODUCT_MODIFY',
                'PRODUCT_VIEW']
        return acts + [('PRODUCT_ADMIN', acts)] + [('ROADMAP_ADMIN', acts)]

    # ITicketFieldProvider methods
    def get_select_fields(self):
        """Product select fields"""
        return [(35, {'name': 'product', 'label': N_('Product'),
                      'cls': Product, 'pk': 'prefix', 'optional': True})]

    def get_radio_fields(self):
        """Product radio fields"""
        return []

    # IResourceManager methods

    def get_resource_realms(self):
        """Manage 'product' realm.
        """
        yield 'product'

    def get_resource_description(self, resource, format='default', context=None,
                                 **kwargs):
        """Describe product resource.
        """
        desc = resource.id
        if format != 'compact':
            desc = _('Product %(name)s', name=resource.id)
        if context:
            return self._render_link(context, resource.id, desc)
        else:
            return desc

    def _render_link(self, context, name, label, extra=''):
        """Render link to product page.
        """
        product = Product.select(self.env, where={'name' : name})
        if product:
            product = product[0]
            href = context.href.products(product.prefix)
            if 'PRODUCT_VIEW' in context.perm(product.resource):
                return tag.a(label, class_='product', href=href + extra)
        elif 'PRODUCT_CREATE' in context.perm('product', name):
            return tag.a(label, class_='missing product', 
                    href=context.href('products', action='new'),
                    rel='nofollow')
        return tag.a(label, class_='missing product')

    def resource_exists(self, resource):
        """Check whether product exists physically.
        """
        products = Product.select(self.env, where={'name' : resource.id})
        return bool(products)

