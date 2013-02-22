
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

import copy

from pkg_resources import resource_filename
from trac.config import Option, PathOption
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

    product_base_url = Option('multiproduct', 'product_base_url', '',
        """A pattern used to generate the base URL of product environments,
        e.g. the use cases listed in bh:wiki:/Proposals/BEP-0003#url-mapping .
        Both absolute as well as relative URLs are supported. The later 
        will be resolved with respect to the base URL of the parent global
        environment. The pattern may contain references to $(prefix)s and 
        $(name)s placeholders representing the product prefix and name
        respectively . If nothing is set the following will be used 
        `products/$(prefix)s`

        Note the usage of `$(...)s` instead of `%(...)s` as the later form 
        would be interpreted by the ConfigParser itself. """)

    product_config_parent = PathOption('inherit', 'multiproduct', '',
        """The path to the configuration file containing the settings shared
        by sibling product environments. By default will inherit 
        global environment configuration.
        """)

    SCHEMA = [mcls._get_schema() \
              for mcls in (Product, ProductResourceMap)]

    # Tables which should be migrated (extended with 'product' column)
    MIGRATE_TABLES = ['enum', 'component', 'milestone', 'version', 'permission', 'wiki']


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
        with self.env.db_direct_transaction as db:
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
                from multiproduct.model import Product
                import trac.db_default

                DEFAULT_PRODUCT = 'default'

                # extend trac default schema by adding product column and extending key with product
                table_defs = [copy.deepcopy(t) for t in trac.db_default.schema if t.name in self.MIGRATE_TABLES]
                for t in table_defs:
                    t.columns.append(Column('product'))
                    if isinstance(t.key, list):
                        t.key = tuple(t.key) + tuple(['product'])
                    elif isinstance(t.key, tuple):
                        t.key = t.key + tuple(['product'])
                    else:
                        raise TracError("Invalid table '%s' schema key '%s' while upgrading "
                                        "plugin '%s' from version %d to %d'" %
                                        (t.name, t.key, PLUGIN_NAME, db_installed_version, 3))
                table_columns = dict()
                for table in table_defs:
                    table_columns[table.name] = filter(lambda column: column != 'product',
                                                         [column.name for column in
                                                            list(filter(lambda t: t.name == table.name,
                                                                                  table_defs)[0].columns)])
                self.log.info("Creating default product")
                default_product = Product(self.env)
                default_product.update_field_dict({'prefix': DEFAULT_PRODUCT,
                                                   'name': 'Default',
                                                   'description': 'Default product',
                                                   'owner': '',
                                                 })
                default_product.insert()

                self.log.info("Migrating tickets w/o product to default product")
                db("""UPDATE ticket SET product='%s'
                        WHERE product=''""" % DEFAULT_PRODUCT)

                self.log.info("Migrating tables to a new schema")
                for table in self.MIGRATE_TABLES:
                    cols = ','.join(table_columns[table])
                    self.log.info("Migrating table '%s' to a new schema", table)
                    db("CREATE TABLE %s_temp AS SELECT %s FROM %s" %
                        (table, cols, table))
                    db("DROP TABLE %s" % table)
                    db_connector, _ = DatabaseManager(self.env)._get_connector()
                    table_schema = filter(lambda t: t.name == table, table_defs)[0]
                    for sql in db_connector.to_sql(table_schema):
                        db(sql)
                    products = Product.select(self.env)
                    for product in products:
                        self.log.info("Populating table '%s' for product '%s' ('%s')", table, product.name, product.prefix)
                        db("INSERT INTO %s (%s, product) SELECT %s,'%s' FROM %s_temp" %
                            (table, cols, cols, product.prefix, table))
                    if table == 'permission':
                        self.log.info("Populating table '%s' for global scope", table)
                        db("INSERT INTO %s (%s, product) SELECT %s,'%s' FROM %s_temp" %
                           (table, cols, cols, '', table))
                    db("DROP TABLE %s_temp" % table)
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
                      'cls': Product, 'pk': 'prefix', 'optional': False})]

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

