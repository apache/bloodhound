# -*- coding: UTF-8 -*-
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

"""Bloodhound product environment and related APIs"""

import os.path
from urlparse import urlsplit
from sqlite3 import OperationalError

from trac.config import BoolOption, ConfigSection, Option
from trac.core import Component, ComponentManager, ExtensionPoint, implements, \
                      ComponentMeta
from trac.db.api import TransactionContextManager, QueryContextManager, \
                        DatabaseManager
from trac.perm import IPermissionRequestor, PermissionSystem
from trac.util import get_pkginfo, lazy
from trac.util.compat import sha1
from trac.util.text import to_unicode, unicode_quote
from trac.versioncontrol import RepositoryManager
from trac.web.href import Href

from multiproduct.api import MultiProductSystem, ISupportMultiProductEnvironment
from multiproduct.cache import lru_cache, default_keymap
from multiproduct.config import Configuration
from multiproduct.dbcursor import BloodhoundConnectionWrapper, BloodhoundIterableCursor, \
                                  ProductEnvContextManager
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

        :param path:   the absolute path to the Trac environment
        :param create: if `True`, the environment is created and
                       populated with default data; otherwise, the
                       environment is expected to already exist.
        :param options: A list of `(section, name, value)` tuples that
                        define configuration options
    """

    multi_product_support_components = ExtensionPoint(ISupportMultiProductEnvironment)

    @property
    def global_setup_participants(self):
        """If multi product schema is enabled, return only setup participants
        that implement ISupportMultiProduct. Otherwise, all setup participants
        are considered global.
        """
        if self._multiproduct_schema_enabled:
            all_participants = self.setup_participants
            multiproduct_aware = set(self.multi_product_support_components)
            priority = lambda x: 0 if isinstance(x, MultiProductSystem) else 10

            return sorted(
                (c for c in all_participants if c in multiproduct_aware),
                key=priority
            )
        else:
            return self.setup_participants

    @property
    def product_setup_participants(self):
        """If multi product schema is enabled, return setup participants that
        need to be instantiated for each product env. Otherwise, return an
        empty list.
        """
        if self._multiproduct_schema_enabled:
            all_participants = self.setup_participants
            multiproduct_aware = set(self.multi_product_support_components)
            return [
                c for c in all_participants if c not in multiproduct_aware
            ]
        else:
            return []

    def __init__(self, path, create=False, options=[]):
        # global environment w/o parent, set these two before super.__init__
        # as database access can take place within trac.env.Environment
        self.parent = None
        self.product = None

        # `trac.env.Environment.__init__` is not invoked as creation is handled differently
        # from base implementation - different setup participants are invoked when creating
        # global environment.
        ComponentManager.__init__(self)

        self.path = path
        self.systeminfo = []
        self._href = self._abs_href = None

        self._multiproduct_schema_enabled = False

        if create:
            self.create(options)
        else:
            self.verify()
            self.setup_config()

        # invoke `IEnvironmentSetupParticipant.environment_created` for all
        # global setup participants
        if create:
            for participant in self.global_setup_participants:
                with ComponentEnvironmentContext(self, participant):
                    participant.environment_created()

    @property
    def db_query(self):
        return ProductEnvContextManager(super(Environment, self).db_query, self) \
            if self._multiproduct_schema_enabled else self.db_direct_query

    @property
    def db_transaction(self):
        return ProductEnvContextManager(super(Environment, self).db_transaction, self) \
            if self._multiproduct_schema_enabled else self.db_direct_transaction

    @property
    def db_direct_query(self):
        return ProductEnvContextManager(super(Environment, self).db_query)

    @property
    def db_direct_transaction(self):
        return ProductEnvContextManager(super(Environment, self).db_transaction)

    def all_product_envs(self):
        return [ProductEnvironment(self, product) for product in Product.select(self)]

    def needs_upgrade(self):
        """Return whether the environment needs to be upgraded."""
        def needs_upgrade_in_env(participant, env):
            with ComponentEnvironmentContext(env, participant):
                with env.db_query as db:
                    if participant.environment_needs_upgrade(db):
                        self.log.warn("component %s.%s requires environment upgrade in environment %s...",
                                      participant.__module__, participant.__class__.__name__,
                                      env)
                        return True
        if any(needs_upgrade_in_env(participant, self)
               for participant in self.global_setup_participants):
            return True

        # until schema is multi product aware, product environments can't (and shouldn't) be
        # instantiated
        if self._multiproduct_schema_enabled:
            if any(needs_upgrade_in_env(participant, env)
                   for env in [self] + self.all_product_envs()
                   for participant in self.product_setup_participants):
                return True
        return False

    def upgrade(self, backup=False, backup_dest=None):
        """Upgrade database.

        :param backup: whether or not to backup before upgrading
        :param backup_dest: name of the backup file
        :return: whether the upgrade was performed
        """
        def upgrader_for_env(participant, env):
            with ComponentEnvironmentContext(env, participant):
                with env.db_query as db:
                    if participant.environment_needs_upgrade(db):
                        self.log.info(
                            "%s.%s needs upgrade in environment %s...",
                            participant.__module__,
                            participant.__class__.__name__,
                            env)
                        return env, participant

        def upgraders_for_product_envs():
            upgraders = (upgrader_for_env(participant, env)
                         for participant in self.product_setup_participants
                         for env in [self] + self.all_product_envs())
            return [u for u in upgraders if u]

        # first enumerate components that are multi product aware and
        # require upgrade in global environment
        global_upgraders = [upgrader_for_env(participant, self)
                            for participant in self.global_setup_participants]
        global_upgraders = [u for u in global_upgraders if u]
        product_upgraders = None
        if not global_upgraders and self._multiproduct_schema_enabled:
            # if no upgrades required in global environment, enumerate
            # required upgrades for product environments
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
                              participant.__module__,
                              participant.__class__.__name__,
                              env)
                with ComponentEnvironmentContext(env, participant):
                    with env.db_transaction as db:
                        participant.upgrade_environment(db)
                # Database schema may have changed, so close all connections
                DatabaseManager(env).shutdown()

        # execute global upgrades first, product environment upgrades next
        execute_upgrades(global_upgraders)
        if product_upgraders is None and self._multiproduct_schema_enabled:
            product_upgraders = upgraders_for_product_envs()
        if product_upgraders:
            execute_upgrades(product_upgraders)
        return True

    def get_version(self, db=None, initial=False):
        """Return the current version of the database.  If the
        optional argument `initial` is set to `True`, the version of
        the database used at the time of creation will be returned.
        """
        rows = self.db_direct_query("""
                SELECT value FROM system WHERE name='%sdatabase_version'
                """ % ('initial_' if initial else ''))
        return (rows and int(rows[0][0])) or 0

    def enable_multiproduct_schema(self, enable=True):
        self._multiproduct_schema_enabled = enable
        BloodhoundIterableCursor.cache_reset()

# replace trac.env.Environment with Environment
trac.env.Environment = Environment


# this must follow the monkey patch (trac.env.Environment) above, otherwise
# trac.test.EnvironmentStub will not be correct as the class will derive from
# not replaced trac.env.Environment
import trac.test

class EnvironmentStub(trac.test.EnvironmentStub):
    """Bloodhound test environment stub

    This class replaces trac.test.EnvironmentStub and extends it with parent
    and product properties (same case as with the Environment).
    """
    def __init__(self, default_data=False, enable=None, disable=None,
                 path=None, destroying=False):
        self.parent = None
        self.product = None

        self._multiproduct_schema_enabled = False

        super(EnvironmentStub, self).__init__(default_data=False,
                                              enable=enable, disable=disable,
                                              path=path, destroying=destroying)
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
        multiproduct_schema = self._multiproduct_schema_enabled
        self._multiproduct_schema_enabled = False
        try:
            super(EnvironmentStub, self).reset_db(default_data=default_data)
        finally:
            self._multiproduct_schema_enabled = multiproduct_schema

# replace trac.test.EnvironmentStub
trac.test.EnvironmentStub = EnvironmentStub


class ProductEnvironment(Component, ComponentManager):
    """Bloodhound product-aware environment manager.

    Bloodhound encapsulates access to product resources stored inside a
    Trac environment via product environments. They are compatible lightweight
    irepresentations of top level environment. 

    Product environments contain among other things:

    * configuration key-value pairs stored in the database,
    * product-aware clones of the wiki and ticket attachments files,

    Product environments do not have:

    * product-specific templates and plugins,
    * a separate database
    * active participation in database upgrades and other setup tasks

    See https://issues.apache.org/bloodhound/wiki/Proposals/BEP-0003
    """
    
    class __metaclass__(ComponentMeta):

        def product_env_keymap(args, kwds, kwd_mark):
            # Remove meta-reference to self (i.e. product env class)
            args = args[1:]
            try:
                product = kwds['product']
            except KeyError:
                # Product provided as positional argument
                if isinstance(args[1], Product):
                    args = (args[0], args[1].prefix) + args[2:]
            else:
                # Product supplied as keyword argument
                if isinstance(product, Product):
                    kwds['product'] = product.prefix
            return default_keymap(args, kwds, kwd_mark)

        @lru_cache(maxsize=100, keymap=product_env_keymap)
        def __call__(self, *args, **kwargs):
            """Return an existing instance of there is a hit 
            in the global LRU cache, otherwise create a new instance.
            """
            return ComponentMeta.__call__(self, *args, **kwargs)

        del product_env_keymap

    implements(trac.env.ISystemInfoProvider, IPermissionRequestor)

    setup_participants = ExtensionPoint(trac.env.IEnvironmentSetupParticipant)
    multi_product_support_components = ExtensionPoint(ISupportMultiProductEnvironment)

    @property
    def product_setup_participants(self):
            return [
                component for component in self.setup_participants
                if component not in self.multi_product_support_components
            ]

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

    _base_url = Option('trac', 'base_url', '',
        """Reference URL for the Trac deployment.
        
        This is the base URL that will be used when producing
        documents that will be used outside of the web browsing
        context, like for example when inserting URLs pointing to Trac
        resources in notification e-mails.""")

    @property
    def base_url(self):
        base_url = self._base_url
        if base_url == self.parent.base_url:
            return ''
        return base_url

    _base_url_for_redirect = BoolOption('trac', 'use_base_url_for_redirect',
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

    def __init__(self, env, product, create=False):
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

        self.setup_config()

        # when creating product environment, invoke `IEnvironmentSetupParticipant.environment_created`
        # for all setup participants that don't support multi product environments
        if create:
            for participant in self.product_setup_participants:
                with ComponentEnvironmentContext(self, participant):
                    participant.environment_created()

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

    # IPermissionRequestor methods
    def get_permission_actions(self):
        """Implement the product-specific `PRODUCT_ADMIN` meta permission.
        """
        actions = set()
        permsys = PermissionSystem(self)
        for requestor in permsys.requestors:
            if requestor is not self and requestor is not permsys:
                for action in requestor.get_permission_actions() or []:
                    if isinstance(action, tuple):
                        actions.add(action[0])
                    else:
                        actions.add(action)
        # PermissionSystem's method was not invoked
        actions.add('EMAIL_VIEW')
        # FIXME: should not be needed, JIC better double check
        actions.discard('TRAC_ADMIN')
        return [('PRODUCT_ADMIN', list(actions))]

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
        # Upgrades are handled by global environment
        return False

    def upgrade(self, backup=False, backup_dest=None):
        """Upgrade database.

        :param backup: whether or not to backup before upgrading
        :param backup_dest: name of the backup file
        :return: whether the upgrade was performed
        """
        # Upgrades handled by global environment
        return True

    @lazy
    def href(self):
        """The application root path"""
        return Href(urlsplit(self.abs_href.base).path)

    @lazy
    def abs_href(self):
        """The application URL"""
        if not self.base_url:
            urlpattern = MultiProductSystem(self.parent).product_base_url
            if not urlpattern:
                self.log.warn("product_base_url option not set in "
                              "configuration, generated links may be "
                              "incorrect")
                urlpattern = 'products/$(prefix)s'
            envname = os.path.basename(self.parent.path)
            prefix = unicode_quote(self.product.prefix, safe="")
            name = unicode_quote(self.product.name, safe="")
            url = urlpattern.replace('$(', '%(') \
                            .replace('%(envname)s', envname) \
                            .replace('%(prefix)s', prefix) \
                            .replace('%(name)s', name)
            if urlsplit(url).netloc:
                #  Absolute URLs
                _abs_href = Href(url)
            else:
                # Relative URLs
                parent_href = Href(self.parent.abs_href(),
                                   path_safe="/!~*'()%",
                                   query_safe="!~*'()%")
                _abs_href = Href(parent_href(url))
        else:
            _abs_href = Href(self.base_url)
        return _abs_href

    # Multi-product API extensions

    @classmethod
    def lookup_global_env(cls, env):
        return env.parent if isinstance(env, ProductEnvironment) else env

    @classmethod
    def lookup_env(cls, env, prefix=None, name=None):
        """Instantiate environment according to product prefix or name

        @throws LookupError if no product matches neither prefix nor name 
        """
        if isinstance(env, ProductEnvironment):
            global_env = env.parent
        else:
            global_env = env

        # FIXME: Update if multiproduct.dbcursor.GLOBAL_PRODUCT != ''
        if not prefix and not name:
            return global_env
        elif isinstance(env, ProductEnvironment) and \
                env.product.prefix == prefix:
            return env
        if prefix:
            try:
                return ProductEnvironment(global_env, prefix)
            except LookupError:
                if not name:
                    raise
        if name:
            # Lookup product by name
            products = Product.select(global_env, where={'name' : name})
            if products:
                return ProductEnvironment(global_env, products[0])
            else:
                raise LookupError("Missing product '%s'" % (name,))
        else:
            raise LookupError("Mising product '%s'" % (prefix or name,))

    @classmethod
    def resolve_href(cls, to_env, at_env):
        """Choose absolute or relative href when generating links to 
        a product (or global) environment.

        @param at_env:        href expansion is taking place in the 
                              scope of this environment 
        @param to_env:        generated URLs point to resources in
                              this environment
        """
        at_href = at_env.abs_href()
        target_href = to_env.abs_href()
        if urlsplit(at_href)[1] == urlsplit(target_href)[1]:
            return to_env.href
        else:
            return to_env.abs_href


lookup_product_env = ProductEnvironment.lookup_env
resolve_product_href = ProductEnvironment.resolve_href

# Override product-specific options
from multiproduct.config import ProductPermissionPolicyOption
PermissionSystem.policies.__class__ = ProductPermissionPolicyOption
