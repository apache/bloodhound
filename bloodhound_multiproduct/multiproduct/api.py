
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

import copy
import os
import shutil

from genshi.builder import tag, Element
from genshi.core import escape, Markup, unescape

from pkg_resources import resource_filename
from trac.attachment import Attachment
from trac.config import Option, PathOption
from trac.core import Component, TracError, implements, Interface
from trac.db import Table, Column, DatabaseManager, Index
import trac.db_default
from trac.env import IEnvironmentSetupParticipant, Environment
from trac.perm import IPermissionRequestor, PermissionCache
from trac.resource import IExternalResourceConnector, IResourceChangeListener,\
                          IResourceManager, ResourceNotFound
from trac.ticket.api import ITicketFieldProvider, ITicketManipulator
from trac.util.text import to_unicode, unquote_label, unicode_unquote
from trac.util.translation import _, N_
from trac.web.chrome import ITemplateProvider, add_warning
from trac.web.main import FakePerm, FakeSession
from trac.wiki.api import IWikiSyntaxProvider
from trac.wiki.parser import WikiParser

from multiproduct.dbcursor import GLOBAL_PRODUCT
from multiproduct.model import Product, ProductResourceMap, ProductSetting
from multiproduct.util import EmbeddedLinkFormatter, IDENTIFIER

__all__ = ['MultiProductSystem', 'PRODUCT_SYNTAX_DELIMITER']

DB_VERSION = 4
DB_SYSTEM_KEY = 'bloodhound_multi_product_version'
PLUGIN_NAME = 'Bloodhound multi product'

class ISupportMultiProductEnvironment(Interface):
    """Extension point interface for components that are aware of multi
    product environment and its specifics.

    Component implementing this interface is handled in a special way in the
    following scenarios:

    * if implementing `IEnvironmentSetupParticipant` interface, the component
      will only be invoked once per global environment creation/upgrade. It is
      up to the component to install/update it's environment specifics (schema,
      possibly files, etc.) for all products. In contrast, components that don't
      implement `ISupportMultiProductEnvironment` interface will be, during
      install/update, invoked per product environment.
    """
    pass

class MultiProductSystem(Component):
    """Creates the database tables and template directories"""

    implements(IEnvironmentSetupParticipant, IExternalResourceConnector,
               IPermissionRequestor, IResourceChangeListener, IResourceManager,
               ISupportMultiProductEnvironment, ITemplateProvider, 
               ITicketFieldProvider, IWikiSyntaxProvider, ITicketManipulator)

    default_product_prefix = Option(
        'multiproduct',
        'default_product_prefix',
        default='@',
        doc="""Prefix used for default product when migrating single-product
        installations to multi-product.""")

    product_base_url = Option('multiproduct', 'product_base_url', '',
        """A pattern used to generate the base URL of product environments,
        e.g. the use cases listed in bh:wiki:/Proposals/BEP-0003#url-mapping .
        Both absolute as well as relative URLs are supported. The later 
        will be resolved with respect to the base URL of the parent global
        environment. The pattern may contain references to $(envname)s,
        $(prefix)s and $(name)s placeholders representing the environment name,
        product prefix and product name respectively . If nothing is set the
        following will be used `products/$(prefix)s`

        Note the usage of `$(...)s` instead of `%(...)s` as the later form 
        would be interpreted by the ConfigParser itself. """)

    product_config_parent = PathOption('inherit', 'multiproduct', '',
        """The path to the configuration file containing the settings shared
        by sibling product environments. By default will inherit 
        global environment configuration.
        """)

    SCHEMA = [mcls._get_schema()
              for mcls in (Product, ProductResourceMap)]

    # Tables which should be migrated (extended with 'product' column)
    MIGRATE_TABLES = ['component',
                      'milestone',
                      'version',
                      'enum',
                      'permission',
                      'wiki',
                      'report',
                      ]

    PRODUCT_POPULATE_TABLES = list(set(MIGRATE_TABLES) - set(['wiki']))

    def get_version(self):
        """Finds the current version of the bloodhound database schema"""
        rows = self.env.db_direct_query("""
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
        needs_upgrade = db_installed_version < DB_VERSION
        if not needs_upgrade:
            self.env.enable_multiproduct_schema(True)
        return needs_upgrade

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


    _system_wiki_list = None
    @property
    def system_wiki_list(self):
        if MultiProductSystem._system_wiki_list is None:
            MultiProductSystem._system_wiki_list = self._get_system_wiki_list()
        return MultiProductSystem._system_wiki_list

    def _get_system_wiki_list(self):
        """Helper function that enumerates all 'system' wikis. The
        list is combined of default wiki pages and pages that are
        bundled with Bloodhound dashboard and search plugins"""
        from bhdashboard import wiki

        paths = [resource_filename('trac.wiki',
                                   'default-pages')] + \
                [resource_filename('bhdashboard',
                                   'default-pages')] + \
                [resource_filename('bhsearch',
                                   'default-pages')]
        pages = []
        original_pages = []
        for path in paths:
            for page in os.listdir(path):
                filename = os.path.join(path, page)
                page = unicode_unquote(page.encode('utf-8'))
                if os.path.isfile(filename):
                    original_pages.append(page)
        for original_name in original_pages:
            if original_name.startswith('Trac'):
                new_name = wiki.new_name(original_name)
                if not new_name:
                    continue
                if new_name in original_pages:
                    continue
                name = new_name
                # original trac wikis should also be included in the list
                pages.append(original_name)
            else:
                name = original_name
            pages.append(name)
        return pages

    def upgrade_environment(self, db_dummy=None):
        """Installs or updates tables to current version"""
        self.log.debug("upgrading existing environment for %s plugin." % 
                       PLUGIN_NAME)
        db_installed_version = self.get_version()
        with self.env.db_direct_transaction as db:
            if db_installed_version < 1:
                self._add_column_product_to_ticket(db)
                self._create_multiproduct_tables(db)
                db_installed_version = self._update_db_version(db, 1)

            if db_installed_version < 2:
                self._replace_product_on_ticket_with_product_prefix(db)
                db_installed_version = self._update_db_version(db, 2)

            if db_installed_version < 3:
                SYSTEM_TABLES = ['system']
                TICKET_TABLES = [
                    'ticket_change', 'ticket_custom', 'attachment',
                ]
                table_defs = self._add_product_column_to_tables(
                    self.MIGRATE_TABLES + TICKET_TABLES + SYSTEM_TABLES,
                    db_installed_version)
                table_columns = self._get_table_columns(table_defs)
                create_temp_table = lambda table: self._create_temp_table(
                    db, table, table_columns, table_defs)

                self._insert_default_product(db)
                self._upgrade_tickets(db, TICKET_TABLES, create_temp_table)
                self._upgrade_wikis(db, create_temp_table)
                self._upgrade_system_tables(db, create_temp_table)
                self._soft_link_repositories_to_default_product(db)
                self._upgrade_table_system(SYSTEM_TABLES, create_temp_table, db)
                self._enable_multiproduct_hooks()

                db_installed_version = self._update_db_version(db, 3)

            if db_installed_version < 4:
                self._create_product_tables_for_plugins(db)
                db_installed_version = self._update_db_version(db, 4)

            self.env.enable_multiproduct_schema(True)

    def _add_column_product_to_ticket(self, db):
        self.log.debug("Adding field product to ticket table")
        db("ALTER TABLE ticket ADD COLUMN product TEXT")

    def _create_multiproduct_tables(self, db):
        self.log.debug("Creating initial db tables for %s plugin." %
                       PLUGIN_NAME)
        db_connector, dummy = DatabaseManager(self.env)._get_connector()
        for table in self.SCHEMA:
            for statement in db_connector.to_sql(table):
                db(statement)

    def _replace_product_on_ticket_with_product_prefix(self, db):
        for prod in Product.select(self.env):
            db("""UPDATE ticket SET product=%s
                          WHERE product=%s""", (prod.prefix, prod.name))

    def _create_temp_table(self, db, table, table_columns, table_defs):
        """creates temporary table with the new schema and
        drops original table"""
        table_temp_name = '%s_temp' % table
        if table == 'report':
            cols = ','.join([c for c in table_columns[table] if c != 'id'])
        else:
            cols = ','.join(table_columns[table])
        self.log.info("Migrating table '%s' to a new schema", table)
        db("""CREATE TABLE %s AS SELECT %s FROM %s""" %
              (table_temp_name, cols, table))
        db("""DROP TABLE %s""" % table)
        db_connector, _ = DatabaseManager(self.env)._get_connector()
        table_schema = [t for t in table_defs if t.name == table][0]
        for sql in db_connector.to_sql(table_schema):
            db(sql)
        return table_temp_name, cols

    def _drop_temp_table(self, db, table):
        db("""DROP TABLE %s""" % table)

    def _add_product_column_to_tables(self, tables, current_version):
        """Extend trac default schema by adding product column
        and extending key with product.
        """
        table_defs = [copy.deepcopy(t) for t in trac.db_default.schema
                      if
                      t.name in tables]
        for t in table_defs:
            t.columns.append(Column('product'))
            if isinstance(t.key, list):
                t.key = tuple(t.key) + tuple(['product'])
            elif isinstance(t.key, tuple):
                t.key = t.key + tuple(['product'])
            else:
                raise TracError(
                    "Invalid table '%s' schema key '%s' while upgrading "
                    "plugin '%s' from version %d to %d'" %
                    (t.name, t.key, PLUGIN_NAME, current_version, 3))
        return table_defs

    def _get_table_columns(self, table_defs):
        table_columns = dict()
        for table in table_defs:
            table_definition = \
                [t for t in table_defs if t.name == table.name][0]
            column_names = \
                [column.name for column in table_definition.columns]
            table_columns[table.name] = \
                [c for c in column_names if c != 'product']
        return table_columns

    def _insert_default_product(self, db):
        self.log.info("Creating default product")
        db("""INSERT INTO bloodhound_product (prefix, name, description, owner)
              VALUES ('%s', '%s', '%s', '')
           """ % (self.default_product_prefix, 'Default', 'Default product'))

    def _upgrade_tickets(self, db, TICKET_TABLES, create_temp_table):
        # migrate tickets that don't have product assigned to default product
        # - update ticket table product column
        # - update ticket related tables by:
        #   - upgrading schema
        #   - update product column to match ticket's product
        self.log.info("Migrating tickets w/o product to default product")
        db("""UPDATE ticket SET product='%s'
                      WHERE (product IS NULL OR product='')
           """ % self.default_product_prefix)
        self._migrate_attachments(
            db("""SELECT a.type, a.id, a.filename
                            FROM attachment a
                      INNER JOIN ticket t ON a.id = %(t.id)s
                           WHERE a.type='ticket'
                       """ % {'t.id': db.cast('t.id', 'text')}),
            to_product=self.default_product_prefix
        )
        self.log.info("Migrating ticket tables to a new schema")
        for table in TICKET_TABLES:
            temp_table_name, cols = create_temp_table(table)
            db("""INSERT INTO %s (%s, product)
                          SELECT %s, '' FROM %s""" %
               (table, cols, cols, temp_table_name))
            self._drop_temp_table(db, temp_table_name)
            if table == 'attachment':
                db("""UPDATE attachment
                         SET product=(SELECT ticket.product
                                        FROM ticket
                                       WHERE %(ticket.id)s=attachment.id
                                       LIMIT 1)
                       WHERE attachment.type='ticket'
                         AND EXISTS(SELECT ticket.product
                                      FROM ticket
                                     WHERE %(ticket.id)s=attachment.id)
                   """ % {'ticket.id': db.cast('ticket.id', 'text')})
            else:
                db("""UPDATE %(table)s
                         SET product=(SELECT ticket.product
                                        FROM ticket
                                       WHERE ticket.id=%(table)s.ticket)
                   """ % {'table': table})

    def _upgrade_system_tables(self, db, create_temp_table):
        # migrate system table (except wiki which is handled separately)
        # to a new schema
        # - create tables with the new schema
        # - populate system tables with global configuration for each product
        # - exception is permission table where permissions
        #   are also populated in global scope
        #
        # permission table specifics: 'anonymous' and 'authenticated' users
        # should by default have a PRODUCT_VIEW permission for all products
        self.log.info("Migrating system tables to a new schema")
        for table in self.MIGRATE_TABLES:
            if table == 'wiki':
                continue
            temp_table_name, cols = create_temp_table(table)
            for product in Product.select(self.env):
                self.log.info("Populating table '%s' for product '%s' ('%s')",
                              table, product.name, product.prefix)
                db("""INSERT INTO %s (%s, product) SELECT %s,'%s' FROM %s""" %
                   (table, cols, cols, product.prefix, temp_table_name))
                if table == 'permission':
                    db.executemany(
                        """INSERT INTO permission (username, action, product)
                           VALUES (%s, %s, %s)""",
                        [('anonymous', 'PRODUCT_VIEW', product.prefix),
                         ('authenticated', 'PRODUCT_VIEW', product.prefix)])

            if table == 'permission':
                self.log.info("Populating table '%s' for global scope", table)
                db("""INSERT INTO %s (%s, product) SELECT %s,'%s' FROM %s""" %
                   (table, cols, cols, '', temp_table_name))
            self._drop_temp_table(db, temp_table_name)
        db.executemany(
            """INSERT INTO permission (username, action, product)
                VALUES (%s, %s, %s)""",
            [('anonymous', 'PRODUCT_VIEW', ''),
             ('authenticated', 'PRODUCT_VIEW', '')])


    def _upgrade_wikis(self, db, create_temp_table):
        # migrate wiki table
        # - populate system wikis to all products + global scope
        # - update wiki attachment product to match wiki product
        table = 'wiki'
        temp_table_name, cols = create_temp_table(table)
        self.log.info("Migrating wikis to default product")
        db("""INSERT INTO %(table)s (%(cols)s, product)
                   SELECT %(cols)s, '%(default_product)s' FROM %(temp_table)s
           """ % dict(table=table,
                      temp_table=temp_table_name,
                      cols=cols,
                      default_product=self.default_product_prefix,))
        db("""UPDATE attachment
                 SET product='%s'
               WHERE attachment.type='wiki'
           """ % self.default_product_prefix)
        self._migrate_attachments(
            db("""SELECT type, id, filename
                    FROM attachment
                   WHERE type='wiki'
                     AND product='%s'
               """ % (self.default_product_prefix)),
            to_product=self.default_product_prefix,
        )
        self._drop_temp_table(db, temp_table_name)

    def _migrate_attachments(self, attachments, to_product=None, copy=False):
        for type, id, filename in attachments:
            old_path = Attachment._get_path(self.env.path, type, id, filename)
            new_path = self.env.path
            if to_product:
                new_path = os.path.join(new_path, 'products', to_product)
            new_path = Attachment._get_path(new_path, type, id, filename)
            dirname = os.path.dirname(new_path)
            if not os.path.exists(old_path):
                self.log.warning(
                    "Missing attachment files for %s:%s/%s",
                    type, id, filename)
                continue
            if os.path.exists(new_path):
                # TODO: Do we want to overwrite?
                continue
            try:
                if not os.path.exists(dirname):
                    os.makedirs(dirname)
                if copy:
                    if hasattr(os, 'link'):
                        # TODO: It this safe?
                        os.link(old_path, new_path)
                    else:
                        shutil.copy(old_path, new_path)
                else:
                    os.rename(old_path, new_path)
            except OSError as err:
                self.log.warning(
                    "Could not move attachment %s from %s %s to"
                    "product @ (%s)",
                    filename, type, id, str(err)
                )

    def _soft_link_repositories_to_default_product(self, db):
        # soft link existing repositories to default product
        repositories_linked = []
        for id, name in db("""SELECT id, value FROM repository
                                      WHERE name='name'"""):
            if id in repositories_linked:
                continue
            db("""INSERT INTO repository (id, name, value)
                          VALUES (%s, 'product', '%s')""" %
               (id, self.default_product_prefix))
            repositories_linked.append(id)
            self.log.info("Repository '%s' (%s) soft linked to default product",
                          name, id)

    def _upgrade_table_system(self, SYSTEM_TABLES, create_temp_table, db):
        # Update system tables
        # Upgrade schema
        self.log.info("Migrating system tables to a new schema")
        for table in SYSTEM_TABLES:
            temp_table_name, cols = create_temp_table(table)
            db("""INSERT INTO %s (%s, product)
                          SELECT %s,'' FROM %s""" %
               (table, cols, cols, temp_table_name))
            self._drop_temp_table(db, temp_table_name)

    def _enable_multiproduct_hooks(self):
        # enable multi product hooks in environment configuration
        import multiproduct.hooks
        import inspect

        config_update = False
        hook_path = os.path.realpath(inspect.getsourcefile(multiproduct.hooks))
        if not 'environment_factory' in self.env.config['trac']:
            self.env.config['trac'].set('environment_factory', hook_path)
            config_update = True
        if not 'request_factory' in self.env.config['trac']:
            self.env.config['trac'].set('request_factory', hook_path)
            config_update = True
        if config_update:
            self.log.info(
                "Enabling multi product hooks in environment configuration")
            self.env.config.save()

    def _create_product_tables_for_plugins(self, db):
        self.log.debug("creating additional db tables for %s plugin." %
                       PLUGIN_NAME)
        db_connector, dummy = DatabaseManager(self.env)._get_connector()
        for statement in db_connector.to_sql(ProductSetting._get_schema()):
            db(statement)

    # IResourceChangeListener methods
    def match_resource(self, resource):
        return isinstance(resource, Product)

    def resource_created(self, resource, context):
        import trac.db_default
        from multiproduct.env import EnvironmentStub

        # Don't populate product database when running from within test
        # environment stub as test cases really don't expect that ...
        if isinstance(self.env, EnvironmentStub):
            return

        product = resource
        self.log.debug("Adding product info (%s) to tables:" % product.prefix)
        with self.env.db_direct_transaction as db:
            # create the default entries for this Product from defaults
            for table in trac.db_default.get_data(db):
                if not table[0] in self.PRODUCT_POPULATE_TABLES:
                    continue

                self.log.debug("  -> %s" % table[0])
                cols = table[1] + ('product', )
                rows = [p + (product.prefix, ) for p in table[2]]
                db.executemany(
                    "INSERT INTO %s (%s) VALUES (%s)" %
                    (table[0], ','.join(cols), ','.join(['%s' for c in cols])),
                    rows)

    def resource_changed(self, resource, old_values, context):
        return

    def resource_deleted(self, resource, context):
        return

    def resource_version_deleted(self, resource, context):
        return

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
        if not isinstance(self.env, ProductEnvironment):
            return acts + [('PRODUCT_ADMIN', acts)] + [('ROADMAP_ADMIN', acts)]
        else:
            # In product context PRODUCT_ADMIN will be provided by product env
            # to ensure it will always be handy
            return acts

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

    def resource_exists(self, resource):
        """Check whether product exists physically.
        """
        products = Product.select(self.env, where={'name' : resource.id})
        return bool(products)

    # IExternalResourceConnector methods
    def get_supported_neighborhoods(self):
        """Neighborhoods for `product` and `global` environments.
        """
        yield 'product'
        yield 'global'

    def load_manager(self, neighborhood):
        """Load global environment or product environment given its prefix
        """
        if neighborhood._realm == 'global':
            # FIXME: ResourceNotFound if neighborhood ID != None ?
            prefix = GLOBAL_PRODUCT
        elif neighborhood._realm == 'product':
            prefix = neighborhood._id
        else:
            raise ResourceNotFound(_(u'Unsupported neighborhood %(realm)s', 
                                     realm=neighborhood._realm))
        try:
            return lookup_product_env(self.env, prefix)
        except LookupError:
            raise ResourceNotFound(_(u'Unknown product prefix %(prefix)s', 
                                     prefix=prefix))

    def manager_exists(self, neighborhood):
        """Check whether the target environment exists physically.
        """
        if neighborhood._realm == 'global':
            # Global environment
            return isinstance(self.env, (Environment, ProductEnvironment))
        elif neighborhood._realm == 'product':
            prefix = neighborhood._id
            if not prefix:
                # Global environment
                return True
            return Product(lookup_product_env(self.env, GLOBAL_PRODUCT), 
                           {'prefix' : prefix})._exists

    # IWikiSyntaxProvider methods

    short_syntax_delimiter = u'->'

    def get_wiki_syntax(self):
        yield (r'(?<!\S)!?(?P<pid>%s)%s(?P<ptarget>%s:(?:%s)|%s|%s(?:%s*%s)?)' %
                    (IDENTIFIER,
                     PRODUCT_SYNTAX_DELIMITER_RE,
                     WikiParser.LINK_SCHEME, WikiParser.QUOTED_STRING, 
                     WikiParser.QUOTED_STRING, WikiParser.SHREF_TARGET_FIRST, 
                     WikiParser.SHREF_TARGET_MIDDLE, WikiParser.SHREF_TARGET_LAST),
               lambda f, m, fm : 
                    self._format_link(f, 'product', 
                                      '%s:%s' % (fm.group('pid'), 
                                                 unquote_label(fm.group('ptarget'))),
                                      fm.group(0), fm))
        if self.env[ProductTicketModule] is not None:
            yield (r"(?<!\S)!?(?P<jtp>%s)-(?P<jtt>\d+)(?P<jtf>[?#]\S+)?" %
                        (IDENTIFIER,),
                   lambda f, m, fm : 
                        self._format_link(f, 'product', 
                                          '%s:ticket:%s' % 
                                                (fm.group('jtp'), 
                                                 fm.group('jtt') +
                                                 (fm.group('jtf') or '')), 
                                          m, fm))
 
    def get_link_resolvers(self):
        yield ('global', self._format_link)
        yield ('product', self._format_link)

    # ITicketManipulator methods
    def validate_ticket(self, req, ticket):
        # check whether the owner exists in db, add a warning if not
        if req.args.get('action') == 'reassign' and \
           ticket['owner'] != self.env.config.get('ticket', 'default_owner'):
            owner = self.env.db_direct_query(
                "SELECT sid FROM session WHERE sid=%s",
                (ticket['owner'], ))
            if not owner:
                # Note: add_warning() is used intead of returning a list of
                # error tuples, since the latter results in trac rendering
                # errors (ticket's change.date is not populated)
                add_warning(req, _('The user "%s" does not exist.' %
                    ticket['owner']))
        return []


    # Internal methods

    def _render_link(self, context, name, label, extra='', prefix=None):
        """Render link to product page.
        """
        product_env = product = None
        env = self.env
        if isinstance(env, ProductEnvironment):
            if (prefix is not None and env.product.prefix == prefix) \
                    or (prefix is None and env.name == name): 
                product_env = env
            env = env.parent
        try:
            if product_env is None:
                if prefix is not None:
                    product_env = ProductEnvironment(env, to_unicode(prefix))
                else:
                    product = Product.select(env, 
                                             where={'name' : to_unicode(name)})
                    if not product:
                        raise LookupError("Missing product")
                    product_env = ProductEnvironment(env, 
                                                     to_unicode(product[0]))
        except LookupError:
            pass

        if product_env is not None:
            product = product_env.product
            href = resolve_product_href(to_env=product_env, at_env=self.env)
            if 'PRODUCT_VIEW' in context.perm(product.resource):
                return tag.a(label, class_='product', href=href() + extra,
                             title=product.name)
        if 'PRODUCT_CREATE' in context.perm('product', name):
            params = [('action', 'new')]
            if prefix:
                params.append( ('prefix', prefix) )
            if name:
                params.append( ('name', name) )
            return tag.a(label, class_='missing product', 
                    href=env.href('products', params),
                    rel='nofollow')
        return tag.a(label, class_='missing product')

    def _format_link(self, formatter, ns, target, label, fullmatch):
        link, params, fragment = formatter.split_link(target)
        expr = link.split(':', 1)
        if ns == 'product' and len(expr) == 1:
            # product:prefix form
            return self._render_link(formatter.context, None, label, 
                                     params + fragment, expr[0])
        elif ns == 'global' or (ns == 'product' and expr[0] == ''):
            # global scope
            sublink = link if ns == 'global' else expr[1]
            target_env = self.env.parent \
                            if isinstance(self.env, ProductEnvironment) \
                            else self.env
            return self._make_sublink(target_env, sublink, formatter, ns, 
                                      target, label, fullmatch, 
                                      extra=params + fragment)
        else:
            # product:prefix:realm:id:...
            prefix, sublink = expr
            try:
                target_env = lookup_product_env(self.env, prefix)
            except LookupError:
                return tag.a(label, class_='missing product')
            # TODO: Check for nested product links 
            # e.g. product:p1:product:p2:ticket:1 
            return self._make_sublink(target_env, sublink, formatter, ns,
                                      target, label, fullmatch,
                                      extra=params + fragment)

    FakePermClass = FakePerm

    def _make_sublink(self, env, sublink, formatter, ns, target, label, 
                      fullmatch, extra=''):
        parent_match = {'ns' : ns,
                        'target' : target,
                        'label': Markup(escape(unescape(label)
                                               if isinstance(label, Markup)
                                               else label)),
                        'fullmatch' : fullmatch,
                        }

        # Tweak nested context to work in target product/global scope 
        subctx = formatter.context.child()
        subctx.href = resolve_product_href(to_env=env, at_env=self.env)
        try:
            req = formatter.context.req
        except AttributeError:
            pass
        else:
            # Authenticate in local context but use foreign permissions
            subctx.perm = self.FakePermClass() \
                            if isinstance(req.session, FakeSession) \
                            else PermissionCache(env, req.authname)
            subctx.req = req

        subformatter = EmbeddedLinkFormatter(env, subctx, parent_match)
        subformatter.auto_quote = True
        ctxtag = '[%s] ' % (env.product.prefix,) \
                    if isinstance(env, ProductEnvironment) \
                    else '<global> ' 
        subformatter.enhance_link = lambda link : (
                                link(title=ctxtag + link.attrib.get('title')) 
                                if isinstance(link, Element) 
                                    and 'title' in link.attrib 
                                else link)
        link = subformatter.match(sublink + extra)
        if link:
            return link
        else:
            # Return outermost match unchanged like if it was !-escaped
            for itype, match in fullmatch.groupdict().items():
                if match and not itype in formatter.wikiparser.helper_patterns:
                    return escape(match)


PRODUCT_SYNTAX_DELIMITER = MultiProductSystem.short_syntax_delimiter
PRODUCT_SYNTAX_DELIMITER_RE = ''.join('[%s]' % c 
                                      for c in PRODUCT_SYNTAX_DELIMITER)

from multiproduct.env import ProductEnvironment, lookup_product_env, \
        resolve_product_href
from multiproduct.ticket.web_ui import ProductTicketModule
