
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

from pkg_resources import resource_filename
from trac.core import Component, TracError, implements
from trac.db import Table, Column, DatabaseManager
from trac.env import IEnvironmentSetupParticipant
from trac.web.chrome import ITemplateProvider

class MultiProductSystem(Component):
    """Creates the database tables and template directories"""
    
    implements(IEnvironmentSetupParticipant, ITemplateProvider)
    
    SCHEMA = [
        Table('bloodhound_product', key = ['prefix', 'name']) [
            Column('prefix'),
            Column('name'),
            Column('description'),
            Column('owner'),
            ],
        Table('bloodhound_productresourcemap', key = 'id') [
            Column('id', auto_increment=True),
            Column('product_id'),
            Column('resource_type'),
            Column('resource_id'),
            ]
        ]
    
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
                
                db_connector, _ = DatabaseManager(self.env)._get_connector()
                for table in self.SCHEMA:
                    for statement in db_connector.to_sql(table):
                        db(statement)
                db_installed_version = self.get_version()
    
    # ITemplateProvider methods
    def get_templates_dirs(self):
        """provide the plugin templates"""
        return [resource_filename(__name__, 'templates')]
    
    def get_htdocs_dirs(self):
        """proved the plugin htdocs"""
        return []

