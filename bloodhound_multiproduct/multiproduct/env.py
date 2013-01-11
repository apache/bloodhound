
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

from trac.config import ConfigSection, Option
from trac.core import Component, ComponentManager, implements
from trac.db.api import with_transaction, TransactionContextManager, QueryContextManager
from trac.util import get_pkginfo, lazy
from trac.util.compat import sha1
from trac.versioncontrol import RepositoryManager
from trac.web.href import Href

import trac.env

from multiproduct.model import Product
from multiproduct.dbcursor import BloodhoundIterableCursor

class Environment(trac.env.Environment):
    """Bloodhound environment manager

    This class is intended as monkey-patch replacement for
    trac.env.Environment. Required database access methods/properties
    are replaced to provide global view of the database in contrast
    to ProductEnvironment that features per-product view of the database
    (in the context of selected product).
    """
    def __init__(self, path, create=False, options=[]):
        super(Environment, self).__init__(path, create=create, options=options)
        # global environment w/o parent
        self.env = None
        self.product = None

    @property
    def db_query(self):
        BloodhoundIterableCursor.set_env(self)
        return super(Environment, self).db_query

    @property
    def db_transaction(self):
        BloodhoundIterableCursor.set_env(self)
        return super(Environment, self).db_transaction

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
    def system_info_providers(self):
        r"""System info will still be determined by the global environment.
        """
        return self.env.system_info_providers

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

    # TODO: Estimate product base URL considering global base URL, pattern, ...
    base_url = ''

    # TODO: Estimate product base URL considering global base URL, pattern, ...
    base_url_for_redirect = ''

    @property
    def secure_cookies(self):
        """Restrict cookies to HTTPS connections.
        """
        return self.env.secure_cookies

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
        return self.env.project_url

    project_admin = Option('project', 'admin', '',
        """E-Mail address of the product's leader / administrator.""")

    @property
    def project_admin_trac_url(self):
        """Base URL of a Trac instance where errors in this Trac
        should be reported.
        """
        return self.env.project_admin_trac_url

    # FIXME: Should products have different values i.e. config option ?
    @property
    def project_footer(self):
        """Page footer text (right-aligned).
        """
        return self.env.project_footer

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

        self.env = env
        self.product = product
        self.path = self.env.path
        self.systeminfo = []
        self._href = self._abs_href = None

        self.setup_config()

    # ISystemInfoProvider methods

    def get_system_info(self):
        return self.env.get_system_info()

    # Same as parent environment's . Avoid duplicated code
    component_activated = trac.env.Environment.component_activated.im_func
    _component_name = trac.env.Environment._component_name.im_func
    _component_rules = trac.env.Environment._component_rules
    enable_component = trac.env.Environment.enable_component.im_func
    get_known_users = trac.env.Environment.get_known_users.im_func
    get_systeminfo = trac.env.Environment.get_system_info.im_func
    get_repository = trac.env.Environment.get_repository.im_func
    is_component_enabled = trac.env.Environment.is_component_enabled.im_func

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
        # share connection pool with global environment
        return self.env.get_db_cnx()

    @lazy
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
        return self.env.db_exc()

    def with_transaction(self, db=None):
        """Decorator for transaction functions :deprecated:"""
        return with_transaction(self, db)

    def get_read_db(self):
        """Return a database connection for read purposes :deprecated:

        See `trac.db.api.get_read_db` for detailed documentation."""
        # database connection is shared with global environment
        return self.env.get_read_db()

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
        BloodhoundIterableCursor.set_env(self)
        return QueryContextManager(self.env)

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
        BloodhoundIterableCursor.set_env(self)
        return TransactionContextManager(self.env)

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

    def get_version(self, db=None, initial=False):
        """Return the current version of the database.  If the
        optional argument `initial` is set to `True`, the version of
        the database used at the time of creation will be returned.

        In practice, for database created before 0.11, this will
        return `False` which is "older" than any db version number.

        :since: 0.11

        :since 1.0: deprecation warning: the `db` parameter is no
                    longer used and will be removed in version 1.1.1
        """
        return self.env.get_version(db, initial)

    def setup_config(self):
        """Load the configuration object.
        """
        # FIXME: Install product-specific configuration object
        self.config = self.env.config
        self.setup_log()

    def get_templates_dir(self):
        """Return absolute path to the templates directory.
        """
        return self.env.get_templates_dir()

    def get_htdocs_dir(self):
        """Return absolute path to the htdocs directory."""
        return self.env.get_htdocs_dir()

    def get_log_dir(self):
        """Return absolute path to the log directory."""
        return self.env.get_log_dir()

    def setup_log(self):
        """Initialize the logging sub-system."""
        from trac.log import logger_handler_factory
        logtype = self.log_type
        self.env.log.debug("Log type '%s' for product '%s'", 
                logtype, self.product.prefix)
        if logtype == 'inherit':
            logtype = self.env.log_type
            logfile = self.env.log_file
            format = self.env.log_format
        else:
            logfile = self.log_file
            format = self.log_format
        if logtype == 'file' and not os.path.isabs(logfile):
            logfile = os.path.join(self.get_log_dir(), logfile)
        logid = 'Trac.%s.%s' % \
                (sha1(self.env.path).hexdigest(), self.product.prefix)
        if format:
            format = format.replace('$(', '%(') \
                     .replace('%(path)s', self.path) \
                     .replace('%(basename)s', os.path.basename(self.path)) \
                     .replace('%(project)s', self.project_name)
        self.log, self._log_handler = logger_handler_factory(
            logtype, logfile, self.log_level, logid, format=format)

        from trac import core, __version__ as VERSION
        self.log.info('-' * 32 + ' environment startup [Trac %s] ' + '-' * 32,
                      get_pkginfo(core).get('version', VERSION))

    def backup(self, dest=None):
        """Create a backup of the database.

        :param dest: Destination file; if not specified, the backup is
                     stored in a file called db_name.trac_version.bak
        """
        return self.env.backup(dest)

    def needs_upgrade(self):
        """Return whether the environment needs to be upgraded."""
        #for participant in self.setup_participants:
        #    with self.db_query as db:
        #        if participant.environment_needs_upgrade(db):
        #            self.log.warn("Component %s requires environment upgrade",
        #                          participant)
        #            return True

        # FIXME: For the time being no need to upgrade the environment
        # TODO: Determine the role of product environments at upgrade time
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

    @property
    def href(self):
        """The application root path"""
        if not self._href:
            self._href = Href(urlsplit(self.abs_href.base)[2])
        return self._href

    @property
    def abs_href(self):
        """The application URL"""
        if not self._abs_href:
            if not self.base_url:
                self.log.warn("base_url option not set in configuration, "
                              "generated links may be incorrect")
                self._abs_href = Href('')
            else:
                self._abs_href = Href(self.base_url)
        return self._abs_href

