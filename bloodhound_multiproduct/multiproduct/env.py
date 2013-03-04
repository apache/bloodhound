
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

"""Bloodhound product environment and related APIs"""

import os.path
from urlparse import urlsplit
from sqlite3 import OperationalError

from trac.config import BoolOption, ConfigSection, Option
from trac.core import Component, ComponentManager, implements, Interface, ExtensionPoint
from trac.db.api import TransactionContextManager, QueryContextManager, DatabaseManager
from trac.util import get_pkginfo, lazy
from trac.util.compat import sha1
from trac.versioncontrol import RepositoryManager
from trac.web.href import Href

from multiproduct.api import MultiProductSystem, ISupportMultiProductEnvironment
from multiproduct.config import Configuration
from multiproduct.dbcursor import ProductEnvContextManager, BloodhoundConnectionWrapper
from multiproduct.model import Product

import trac.env

class ComponentEnvironmentContext(object):
    def __init__(self, env, component):
        self._env = env
        self._component = component
    def __enter__(self):
        self._old_env = self._component.env
        self._env.component_activated(self._component)
        return self
    def __exit__(self, type, value, traceback):
        self._old_env.component_activated(self._component)

class Environment(trac.env.Environment):
    """Bloodhound environment manager

    This class is intended as monkey-patch replacement for
    trac.env.Environment. Required database access methods/properties
    are replaced to provide global view of the database in contrast
    to ProductEnvironment that features per-product view of the database
    (in the context of selected product).
    """

    multi_product_support_components = ExtensionPoint(ISupportMultiProductEnvironment)

    def __init__(self, path, create=False, options=[]):
        # global environment w/o parent, set these two before super.__init__
        # as database access can take place within trac.env.Environment
        self.parent = None
        self.product = None
        super(Environment, self).__init__(path, create=create, options=options)
        self._global_setup_participants = set.intersection(set(self.setup_participants),
                                                           set(self.multi_product_support_components))
        self._product_setup_participants = [participant for participant in self.setup_participants
                                                if not participant in self._global_setup_participants]

    @property
    def db_query(self):
        return ProductEnvContextManager(super(Environment, self).db_query, self)

    @property
    def db_transaction(self):
        return ProductEnvContextManager(super(Environment, self).db_transaction, self)

    @property
    def db_direct_query(self):
        return ProductEnvContextManager(super(Environment, self).db_query)

    @property
    def db_direct_transaction(self):
        return ProductEnvContextManager(super(Environment, self).db_transaction)

    def needs_upgrade(self):
        """Return whether the environment needs to be upgraded."""
        def needs_upgrade_in_env_list(env_list, participants):
            for env in env_list:
                for participant in participants:
                    # make sure to skip anything but global environment for multi
                    # product aware components
                    if participant in self._global_setup_participants and \
                       not env == self:
                        continue
                    with ComponentEnvironmentContext(env, participant):
                        with env.db_query as db:
                            if participant.environment_needs_upgrade(db):
                                self.log.warn("component %s.%s requires environment upgrade in environment %s...",
                                              participant.__module__, participant.__class__.__name__,
                                              env)
                                return True
        if needs_upgrade_in_env_list([self], self._global_setup_participants):
            return True
        product_envs = [self] + [ProductEnvironment(self, product) for product in Product.select(self)]
        if needs_upgrade_in_env_list(product_envs, self._product_setup_participants):
            return True
        return False

    def upgrade(self, backup=False, backup_dest=None):
        """Upgrade database.

        :param backup: whether or not to backup before upgrading
        :param backup_dest: name of the backup file
        :return: whether the upgrade was performed
        """
        def upgraders_for_env_list(env_list, participants):
            upgraders = []
            if not participants:
                return upgraders
            for env in env_list:
                for participant in participants:
                    # skip global participants in non-global environments
                    if participant in self._global_setup_participants and \
                        not env == self:
                        continue
                    with ComponentEnvironmentContext(env, participant):
                        with env.db_query as db:
                            if participant.environment_needs_upgrade(db):
                                self.log.info("%s.%s needs upgrade in environment %s...",
                                              participant.__module__, participant.__class__.__name__,
                                              env)
                                upgraders.append((env, participant))
            return upgraders

        def upgraders_for_product_envs():
            product_envs = [self] + [ProductEnvironment(self, product) for product in Product.select(self)]
            return upgraders_for_env_list(product_envs, self._product_setup_participants)

        # first enumerate components that are multi product aware and require upgrade
        # in global environment
        global_upgraders = upgraders_for_env_list([self], self._global_setup_participants)
        product_upgraders = None
        if not global_upgraders:
            # if no upgrades required in global environment, enumerate required upgrades
            # for product environments
            product_upgraders = upgraders_for_product_envs()

        if not global_upgraders + (product_upgraders or []):
            return False

        if backup:
            try:
                self.backup(backup_dest)
            except Exception, e:
                raise trac.env.BackupError(e)

        def execute_upgrades(upgraders_list):
            for env, participant in upgraders_list:
                self.log.info("%s.%s upgrading in environment %s...",
                              participant.__module__, participant.__class__.__name__,
                              env)
                with ComponentEnvironmentContext(env, participant):
                    with env.db_transaction as db:
                        participant.upgrade_environment(db)
                # Database schema may have changed, so close all connections
                DatabaseManager(env).shutdown()

        # execute global upgrades first, product environment upgrades next
        if global_upgraders:
            execute_upgrades(global_upgraders)
        if product_upgraders == None:
            product_upgraders = upgraders_for_product_envs()
        if product_upgraders:
            execute_upgrades(product_upgraders)
        return True

# replace trac.env.Environment with Environment
trac.env.Environment = Environment

def _environment_setup_environment_created(self):
    """Insert default data into the database.

    This code is copy pasted from trac.env.EnvironmentSetup with a slight change
    of using direct (non-translated) transaction to setup default data.
    """
    from trac import db_default
    with self.env.db_direct_transaction as db:
        for table, cols, vals in db_default.get_data(db):
            db.executemany("INSERT INTO %s (%s) VALUES (%s)"
                           % (table, ','.join(cols), ','.join(['%s' for c in cols])),
                              vals)
    self._update_sample_config()

# replace trac.env.EnvironmentSetup.environment_created with the patched version
trac.env.EnvironmentSetup.environment_created = _environment_setup_environment_created

# this must follow the monkey patch (trac.env.Environment) above, otherwise
# trac.test.EnvironmentStub will not be correct as the class will derive from
# not replaced trac.env.Environment
import trac.test

class EnvironmentStub(trac.test.EnvironmentStub):
    """Bloodhound test environment stub

    This class replaces trac.test.EnvironmentStub and extends it with parent and product
    properties (same case as with the Environment).
    """
    def __init__(self, default_data=False, enable=None, disable=None,
                 path=None, destroying=False):
        self.parent = None
        self.product = None
        self.mpsystem = None
        super(EnvironmentStub, self).__init__(default_data=False,
                                              enable=enable, disable=disable,
                                              path=path, destroying=destroying)
        # Apply multi product upgrades. This is required as the database proxy (translator)
        # is installed in any case, we want it to see multi-product enabled database
        # schema...
        self.mpsystem = MultiProductSystem(self)
        try:
            self.mpsystem.upgrade_environment()
        except OperationalError:
            pass

        if default_data:
            self.reset_db(default_data)

    @staticmethod
    def enable_component_in_config(env, cls):
        """Keep track of enabled state in configuration as well 
        during test runs. This is closer to reality than 
        inherited `enable_component` method.
        """
        env.config['components'].set(env._component_name(cls), 'enabled')
        env.enabled.clear()
        env.components.pop(cls, None)
        try:
            del env._rules
        except AttributeError:
            pass
        # FIXME: Shall we ?
        #env.config.save()

    @staticmethod
    def disable_component_in_config(env, component):
        """Keep track of disabled state in configuration as well 
        during test runs. This is closer to reality than 
        inherited `disable_component` method.
        """
        if isinstance(component, type):
            cls = component
        else:
            cls = component.__class__
        env.config['components'].set(env._component_name(cls), 'disabled')
        env.enabled.clear()
        env.components.pop(cls, None)
        try:
            del env._rules
        except AttributeError:
            pass
        # FIXME: Shall we ?
        #env.config.save()

    def reset_db(self, default_data=None):
        from multiproduct.api import DB_VERSION
        schema_version = -1
        if self.mpsystem:
            schema_version = self.mpsystem.get_version()
        super(EnvironmentStub, self).reset_db(default_data=default_data)
        if self.mpsystem and schema_version != -1:
            with self.db_direct_transaction as db:
                self.mpsystem._update_db_version(db, DB_VERSION)


# replace trac.test.EnvironmentStub
trac.test.EnvironmentStub = EnvironmentStub

class ProductEnvironment(Component, ComponentManager):
    """Bloodhound product-aware environment manager.

    Bloodhound encapsulates access to product resources stored inside a
    Trac environment via product environments. They are compatible lightweight
    irepresentations of top level environment. 

    Product environments contain among other things:

    * a configuration file, 
    * product-aware clones of the wiki and ticket attachments files,

    Product environments do not have:

    * product-specific templates and plugins,
    * a separate database
    * active participation in database upgrades and other setup tasks

    See https://issues.apache.org/bloodhound/wiki/Proposals/BEP-0003
    """

    implements(trac.env.ISystemInfoProvider)

    @property
    def setup_participants(self):
        """Setup participants list for product environments will always
        be empty based on the fact that upgrades will only be handled by
        the global environment.
        """
        return ()

    components_section = ConfigSection('components',
        """This section is used to enable or disable components
        provided by plugins, as well as by Trac itself.

        See also: TracIni , TracPlugins
        """)

    @property
    def shared_plugins_dir():
        """Product environments may not add plugins.
        """
        return ''

    base_url = Option('trac', 'base_url', '',
        """Reference URL for the Trac deployment.
        
        This is the base URL that will be used when producing
        documents that will be used outside of the web browsing
        context, like for example when inserting URLs pointing to Trac
        resources in notification e-mails.""")

    base_url_for_redirect = BoolOption('trac', 'use_base_url_for_redirect',
            False, 
        """Optionally use `[trac] base_url` for redirects.
        
        In some configurations, usually involving running Trac behind
        a HTTP proxy, Trac can't automatically reconstruct the URL
        that is used to access it. You may need to use this option to
        force Trac to use the `base_url` setting also for
        redirects. This introduces the obvious limitation that this
        environment will only be usable when accessible from that URL,
        as redirects are frequently used. ''(since 0.10.5)''""")

    @property
    def project_name(self):
        """Name of the product.
        """
        return self.product.name

    @property
    def project_description(self):
        """Short description of the product.
        """
        return self.product.description

    @property
    def project_url(self):
        """URL of the main project web site, usually the website in
        which the `base_url` resides. This is used in notification
        e-mails.
        """
        # FIXME: Should products have different values i.e. config option ?
        return self.parent.project_url

    project_admin = Option('project', 'admin', '',
        """E-Mail address of the product's leader / administrator.""")

    @property
    def project_footer(self):
        """Page footer text (right-aligned).
        """
        # FIXME: Should products have different values i.e. config option ?
        return self.parent.project_footer

    project_icon = Option('project', 'icon', 'common/trac.ico',
        """URL of the icon of the product.""")

    log_type = Option('logging', 'log_type', 'inherit',
        """Logging facility to use.

        Should be one of (`inherit`, `none`, `file`, `stderr`, 
        `syslog`, `winlog`).""")

    log_file = Option('logging', 'log_file', 'trac.log',
        """If `log_type` is `file`, this should be a path to the
        log-file.  Relative paths are resolved relative to the `log`
        directory of the environment.""")

    log_level = Option('logging', 'log_level', 'DEBUG',
        """Level of verbosity in log.

        Should be one of (`CRITICAL`, `ERROR`, `WARN`, `INFO`, `DEBUG`).""")

    log_format = Option('logging', 'log_format', None,
        """Custom logging format.

        If nothing is set, the following will be used:

        Trac[$(module)s] $(levelname)s: $(message)s

        In addition to regular key names supported by the Python
        logger library (see
        http://docs.python.org/library/logging.html), one could use:

        - $(path)s     the path for the current environment
        - $(basename)s the last path component of the current environment
        - $(project)s  the project name

        Note the usage of `$(...)s` instead of `%(...)s` as the latter form
        would be interpreted by the ConfigParser itself.

        Example:
        `($(thread)d) Trac[$(basename)s:$(module)s] $(levelname)s: $(message)s`

        ''(since 0.10.5)''""")

    def __init__(self, env, product):
        """Initialize the product environment.

        :param env:     the global Trac environment
        :param product: product prefix or an instance of
                        multiproduct.model.Product
        """
        if not isinstance(env, trac.env.Environment):
            cls = self.__class__
            raise TypeError("Initializer must be called with " \
                "trac.env.Environment instance as first argument " \
                "(got %s instance instead)" % 
                         (cls.__module__ + '.' + cls.__name__, ))

        ComponentManager.__init__(self)

        if isinstance(product, Product):
            if product._env is not env:
                raise ValueError("Product's environment mismatch")
        elif isinstance(product, basestring):
            products = Product.select(env, where={'prefix': product})
            if len(products) == 1 :
                product = products[0]
            else:
                env.log.debug("Products for '%s' : %s",
                        product, products)
                raise LookupError("Missing product %s" % (product,))

        self.parent = env
        self.product = product
        self.systeminfo = []
        self._href = self._abs_href = None

        self.setup_config()

    def __getitem__(self, cls):
        if issubclass(cls, trac.env.Environment):
            return self.parent
        elif cls is self.__class__:
            return self
        else:
            return ComponentManager.__getitem__(self, cls)

    def __getattr__(self, attrnm):
        """Forward attribute access request to parent environment.

        Initially this will affect the following members of
        `trac.env.Environment` class:

        system_info_providers, secure_cookies, project_admin_trac_url,
        get_system_info, get_version, get_templates_dir, get_templates_dir,
        get_log_dir, backup
        """
        try:
            if attrnm in ('parent', '_rules'):
                raise AttributeError
            return getattr(self.parent, attrnm)
        except AttributeError:
            raise AttributeError("'%s' object has no attribute '%s'" %
                    (self.__class__.__name__, attrnm))

    def __repr__(self):
        return "<%s %s at %s>" % (self.__class__.__name__, 
                                 repr(self.product.prefix),
                                 hex(id(self)))

    @lazy
    def path(self):
        """The subfolder `./products/<product prefix>` relative to the 
        top-level directory of the global environment will be the root of 
        product file system area.
        """
        folder = os.path.join(self.parent.path, 'products', self.product.prefix)
        if not os.path.exists(folder):
            os.makedirs(folder)
        return folder

    # ISystemInfoProvider methods

    # Same as parent environment's . Avoid duplicated code
    component_activated = trac.env.Environment.component_activated.im_func
    _component_name = trac.env.Environment._component_name.im_func
    _component_rules = trac.env.Environment._component_rules
    enable_component = trac.env.Environment.enable_component.im_func
    get_known_users = trac.env.Environment.get_known_users.im_func
    get_repository = trac.env.Environment.get_repository.im_func

    is_component_enabled_local = trac.env.Environment.is_component_enabled.im_func

    def is_component_enabled(self, cls):
        """Implemented to only allow activation of components already 
        activated in the global environment that are in turn not disabled in
        the configuration.

        This is called by the `ComponentManager` base class when a
        component is about to be activated. If this method returns
        `False`, the component does not get activated. If it returns
        `None`, the component only gets activated if it is located in
        the `plugins` directory of the environment.
        """
        if cls is self.__class__:
            # Prevent lookups in parent env ... will always fail 
            return True
        # FIXME : Maybe checking for ComponentManager is too drastic 
        elif issubclass(cls, ComponentManager):
            # Avoid clashes with overridden Environment's options 
            return False
        elif self.parent[cls] is None:
            return False
        return self.is_component_enabled_local(cls)

    def get_db_cnx(self):
        """Return a database connection from the connection pool

        :deprecated: Use :meth:`db_transaction` or :meth:`db_query` instead

        `db_transaction` for obtaining the `db` database connection
        which can be used for performing any query
        (SELECT/INSERT/UPDATE/DELETE)::

           with env.db_transaction as db:
               ...


        `db_query` for obtaining a `db` database connection which can
        be used for performing SELECT queries only::

           with env.db_query as db:
               ...
        """
        return BloodhoundConnectionWrapper(self.parent.get_db_cnx(), self)

    @property
    def db_exc(self):
        """Return an object (typically a module) containing all the
        backend-specific exception types as attributes, named
        according to the Python Database API
        (http://www.python.org/dev/peps/pep-0249/).

        To catch a database exception, use the following pattern::

            try:
                with env.db_transaction as db:
                    ...
            except env.db_exc.IntegrityError, e:
                ...
        """
        # exception types same as in global environment
        return self.parent.db_exc

    def with_transaction(self, db=None):
        """Decorator for transaction functions :deprecated:
        """
        raise NotImplementedError('Deprecated method')

    def get_read_db(self):
        """Return a database connection for read purposes :deprecated:

        See `trac.db.api.get_read_db` for detailed documentation.
        """
        return BloodhoundConnectionWrapper(self.parent.get_read_db(), self)

    @property
    def db_query(self):
        """Return a context manager which can be used to obtain a
        read-only database connection.

        Example::

            with env.db_query as db:
                cursor = db.cursor()
                cursor.execute("SELECT ...")
                for row in cursor.fetchall():
                    ...

        Note that a connection retrieved this way can be "called"
        directly in order to execute a query::

            with env.db_query as db:
                for row in db("SELECT ..."):
                    ...

        If you don't need to manipulate the connection itself, this
        can even be simplified to::

            for row in env.db_query("SELECT ..."):
                ...

        :warning: after a `with env.db_query as db` block, though the
          `db` variable is still available, you shouldn't use it as it
          might have been closed when exiting the context, if this
          context was the outermost context (`db_query` or
          `db_transaction`).
        """
        return ProductEnvContextManager(QueryContextManager(self.parent), self)

    @property
    def db_transaction(self):
        """Return a context manager which can be used to obtain a
        writable database connection.

        Example::

            with env.db_transaction as db:
                cursor = db.cursor()
                cursor.execute("UPDATE ...")

        Upon successful exit of the context, the context manager will
        commit the transaction. In case of nested contexts, only the
        outermost context performs a commit. However, should an
        exception happen, any context manager will perform a rollback.

        Like for its read-only counterpart, you can directly execute a
        DML query on the `db`::

            with env.db_transaction as db:
                db("UPDATE ...")

        If you don't need to manipulate the connection itself, this
        can also be simplified to::

            env.db_transaction("UPDATE ...")

        :warning: after a `with env.db_transaction` as db` block,
          though the `db` variable is still available, you shouldn't
          use it as it might have been closed when exiting the
          context, if this context was the outermost context
          (`db_query` or `db_transaction`).
        """
        return ProductEnvContextManager(TransactionContextManager(self.parent), self)

    def shutdown(self, tid=None):
        """Close the environment."""
        RepositoryManager(self).shutdown(tid)
        # FIXME: Shared DB so IMO this should not happen ... at least not here
        #DatabaseManager(self).shutdown(tid)
        if tid is None:
            self.log.removeHandler(self._log_handler)
            self._log_handler.flush()
            self._log_handler.close()
            del self._log_handler

    def create(self, options=[]):
        """Placeholder for compatibility when trying to create the basic 
        directory structure of the environment, etc ...

        This method does nothing at all.
        """
        # TODO: Handle options args

    def setup_config(self):
        """Load the configuration object.
        """
        import trac.config

        parent_path = MultiProductSystem(self.parent).product_config_parent
        if parent_path and os.path.isfile(parent_path):
            parents = [trac.config.Configuration(parent_path)]
        else:
            parents = [self.parent.config]
        self.config = Configuration(self.parent, self.product.prefix, parents)
        self.setup_log()

    def setup_log(self):
        """Initialize the logging sub-system."""
        from trac.log import logger_handler_factory
        logtype = self.log_type
        logfile = self.log_file
        format = self.log_format

        self.parent.log.debug("Log type '%s' for product '%s'", 
                logtype, self.product.prefix)

        # Force logger inheritance on identical configuration
        if (logtype, logfile, format) == (self.parent.log_type, 
                self.parent.log_file, self.parent.log_format):
            logtype = 'inherit'

        if logtype == 'inherit':
            self.log = self.parent.log
            self._log_handler = self.parent._log_handler
            self.parent.log.warning("Inheriting parent logger for product '%s'",
                    self.product.prefix)
        else:
            if logtype == 'file' and not os.path.isabs(logfile):
                logfile = os.path.join(self.get_log_dir(), logfile)
            logid = 'Trac.%s.%s' % \
                    (sha1(self.parent.path).hexdigest(), self.product.prefix)
            if format:
                format = format.replace('$(', '%(') \
                         .replace('%(path)s', self.path) \
                         .replace('%(basename)s', os.path.basename(self.path)) \
                         .replace('%(project)s', self.project_name)
            self.log, self._log_handler = logger_handler_factory(
                logtype, logfile, self.log_level, logid, format=format)

        from trac import core, __version__ as VERSION
        self.log.info('-' * 32 + 
                        ' product %s environment startup [Trac %s] ' + 
                        '-' * 32,
                      self.product.prefix,
                      get_pkginfo(core).get('version', VERSION))

    def needs_upgrade(self):
        """Return whether the environment needs to be upgraded."""
        return False

    def upgrade(self, backup=False, backup_dest=None):
        """Upgrade database.

        :param backup: whether or not to backup before upgrading
        :param backup_dest: name of the backup file
        :return: whether the upgrade was performed
        """
        # (Database) upgrades handled by global environment
        # FIXME: True or False ?
        return True

    @lazy
    def href(self):
        """The application root path"""
        if not self._href:
            self._href = Href(urlsplit(self.abs_href.base)[2])
        return self._href

    @lazy
    def abs_href(self):
        """The application URL"""
        if not self._abs_href:
            if not self.base_url:
                urlpattern = MultiProductSystem(self.parent).product_base_url
                if not urlpattern:
                    self.log.warn("product_base_url option not set in "
                                  "configuration, generated links may be "
                                  "incorrect")
                    urlpattern = 'products/$(prefix)s'
                url = urlpattern.replace('$(', '%(') \
                     .replace('%(prefix)s', self.product.prefix) \
                     .replace('%(name)s', self.product.name)
                self._abs_href = Href(self.parent.abs_href(url))
            else:
                self._abs_href = Href(self.base_url)
        return self._abs_href

