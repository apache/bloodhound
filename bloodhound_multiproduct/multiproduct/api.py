
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
from trac.core import Component, TracError, implements
from trac.db import Table, Column, DatabaseManager
from trac.env import IEnvironmentSetupParticipant
from trac.perm import IPermissionRequestor
from trac.resource import IResourceManager
from trac.ticket.api import ITicketFieldProvider
from trac.util.translation import _, N_
from trac.web.chrome import ITemplateProvider

from multiproduct.model import Product, ProductResourceMap

DB_VERSION = 2
DB_SYSTEM_KEY = 'bloodhound_multi_product_version'
PLUGIN_NAME = 'Bloodhound multi product'

class MultiProductSystem(Component):
    """Creates the database tables and template directories"""
    
    implements(IEnvironmentSetupParticipant, ITemplateProvider,
            IPermissionRequestor, ITicketFieldProvider, IResourceManager)
    
    SCHEMA = [mcls._get_schema() for mcls in (Product, ProductResourceMap)]
    del mcls
    
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
    
    def upgrade_environment(self, db_dummy=None):
        """Installs or updates tables to current version"""
        self.log.debug("upgrading existing environment for %s plugin." % 
                       PLUGIN_NAME)
        db_installed_version = self.get_version()
        #cursor = db.cursor()
        with self.env.db_transaction as db:
            if db_installed_version < 0:
                # Initial installation
                db("""
                    INSERT INTO system (name, value) VALUES ('%s','%s')
                    """  % (DB_SYSTEM_KEY, DB_VERSION))
                db("ALTER TABLE ticket ADD COLUMN product TEXT")
                self.log.debug("creating initial db tables for %s plugin." % 
                               PLUGIN_NAME)
                
                db_connector, dummy = DatabaseManager(self.env)._get_connector()
                for table in self.SCHEMA:
                    for statement in db_connector.to_sql(table):
                        db(statement)
                db_installed_version = self.get_version()
            
            if db_installed_version == 1:
                from multiproduct.model import Product
                products = Product.select(self.env)
                for prod in products:
                    db("""UPDATE ticket SET product=%s
                          WHERE product=%s""", (prod.prefix, prod.name))
                
                db("""UPDATE system SET value=%s
                      WHERE name=%s""", (DB_VERSION, DB_SYSTEM_KEY))
                self.log.info("Upgraded multiproduct db schema from version %d"
                              " to %d" % (db_installed_version, DB_VERSION))
    
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

