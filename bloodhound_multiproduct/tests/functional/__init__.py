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

import contextlib
import imp
import os
import sys
import time
import urllib2
from inspect import isclass
from subprocess import call, Popen

from trac.tests import functional
from trac.tests.contentgen import (
    random_page, random_paragraph, random_sentence, random_unique_camel,
    random_word
)
from trac.tests.functional.svntestenv import SvnFunctionalTestEnvironment
from trac.tests.functional.testenv import FunctionalTestEnvironment, ConnectError
from trac.tests.functional.tester import b, FunctionalTester, internal_error, tc
from trac.util.compat import close_fds
from trac.util.text import unicode_quote
from trac.web.href import Href

from multiproduct.api import MultiProductSystem
from multiproduct.env import ProductEnvironment
from multiproduct import hooks
from multiproduct.product_admin import ProductAdminModule
from tests import unittest

#----------------
# Constants
#----------------

from multiproduct.dbcursor import GLOBAL_PRODUCT as GLOBAL_ENV

#----------------
# Product-aware classes for functional tests
#----------------

# TODO: Virtual ABCs for isinstance() checks
class MultiproductFunctionalMixin(object):
    """Mixin class applying multi-product upgrade path upon a given
    functional Trac test environment. Access to the global environment
    is provided at testing time. In order to obtain a compatible test
    environment for a given product @see: `product_test_env` method

    @attention: This class must precede functional test environment class in
                class declaration because it overrides some methods
    """

    @property
    def parent(self):
        return None

    def init(self):
        """Determine the location of Trac source code
        """
        self.bh_install_project = 'trac'
        self.bhmp_upgrade = False
        self.trac_src = os.path.realpath(os.path.join(
                __import__('trac', []).__file__, '..' , '..'))
        self.bh_src = os.path.realpath(os.path.join(
                __import__('multiproduct', []).__file__, '..' , '..', '..'))
        self.htdigest = os.path.join(self.dirname, "htdigest")
        self.htdigest_realm = 'bloodhound'
        print "\nFound Trac source: %s" \
              "\nFound Bloodhound source: %s" % (self.trac_src, self.bh_src)
        super(MultiproductFunctionalMixin, self).init()

    def create(self):
        """Create a new test environment.
        This will set up Bloodhound and authentication by invoking installer
        script, then call :meth:`create_repo`.
        """
        os.mkdir(self.dirname)
        self.create_repo()

        self._bloodhound_install()
        if call([sys.executable,
                 os.path.join(self.trac_src, 'contrib', 'htpasswd.py'), "-c",
                 "-b", self.htpasswd, "admin", "admin"], close_fds=close_fds,
                 cwd=self.command_cwd):
            raise Exception('Unable to setup admin password')
        self.adduser('user')
        self._tracadmin('permission', 'add', 'admin', 'TRAC_ADMIN')

        # Setup Trac logging
        env = self.get_trac_environment()
        env.config.set('logging', 'log_type', 'file')
        for component in self.get_enabled_components():
            env.config.set('components', component, 'enabled')
        env.config.save()
        self.post_create(env)

    def adduser_htpasswd(self, user):
        """Add a user to the environment.  The password will be set
        in htpasswd file to the same as username.
        """
        return super(MultiproductFunctionalMixin, self).adduser(user)

    def adduser_htdigest(self, user):
        """Add a user to the environment.  The password will be set
        in htdigest file to the same as username.
        """
        if call([sys.executable, os.path.join(self.trac_src, 'contrib',
                 'htdigest.py'), '-b', self.htdigest, self.htdigest_realm,
                 user, user], close_fds=close_fds, cwd=self.command_cwd):
            raise Exception('Unable to setup password for user "%s"' % user)

    adduser = adduser_htdigest

    def get_env_href(self, user=None, prefix=None, envname=None):
        """Default implementation just returning href object for global
        environment and failing if product prefix is specified.
        """
        if envname not in (self.bh_install_project, None):
            raise LookupError('Unknown environment ' + repr(envname))
        if prefix is not None:
            self._fail_no_mp_setup()
        parts = urllib2.urlparse.urlsplit(self.url)
        if not user or user == 'anonymous':
            return Href('%s://%s/' % (parts[0], parts[1]))
        else:
            return Href('%s://%s:%s@%s/' % (parts[0], user, user, parts[1]))

    def get_enabled_components(self):
        """Also enable Bloodhound multiproduct plugin.
        """
        return super(MultiproductFunctionalMixin, self).get_enabled_components() + \
                ['multiproduct.*']

    def post_create(self, env):
        self.getLogger = lambda : env.log

        print "Created test environment: %s" % self.dirname

        # Setup URL generation for product environments
        self.get_env_href = self.configure_web_hooks()

        super(MultiproductFunctionalMixin, self).post_create(env)

    def _tracadmin(self, *args, **kwargs):
        """Execute trac-admin command in product or (by default) global context
        """
        do_wait = kwargs.pop('wait', False)
        product_id = kwargs.pop('product', None)
        if product_id is not None and product_id != GLOBAL_ENV:
            if self.bhmp_upgrade and \
                    args[0] not in ProductAdminModule.GLOBAL_COMMANDS:
                args = ('product', 'admin', product_id) + args
            elif not self.bhmp_upgrade:
                self._fail_no_mp_setup()

        super(MultiproductFunctionalMixin, self)._tracadmin(*args, **kwargs)
        if do_wait: # Delay to ensure command executes and caches resets
            time.sleep(5)

    def _tracd_options(self):
        """List options to run tracd server started for the test run.
        """
        return ["--port=%s" % self.port, "-s", "--hostname=127.0.0.1"]

    def start(self):
        """Starts the webserver, and waits for it to come up.

        Notice: Same as inherited method but without basic auth by default
        """
        if 'FIGLEAF' in os.environ:
            exe = os.environ['FIGLEAF']
            if ' ' in exe: # e.g. 'coverage run'
                args = exe.split()
            else:
                args = [exe]
        else:
            args = [sys.executable]
        options = self._tracd_options()
        if 'TRAC_TEST_TRACD_OPTIONS' in os.environ:
            options += os.environ['TRAC_TEST_TRACD_OPTIONS'].split()
        self.get_trac_environment().log.debug('Starting tracd with args ' +
                                              ' '.join(options))
        args.append(os.path.join(self.trac_src, 'trac', 'web',
                                 'standalone.py'))
        server = Popen(args + options + [self.tracdir],
                       stdout=functional.logfile, stderr=functional.logfile,
                       close_fds=close_fds,
                       cwd=self.command_cwd,
                      )
        self.pid = server.pid
        # Verify that the url is ok
        timeout = 30
        while timeout:
            try:
                tc.go(self.url)
                break
            except ConnectError:
                time.sleep(1)
            timeout -= 1
        else:
            raise Exception('Timed out waiting for server to start.')
        tc.url(self.url)

    def restart(self):
        """Restarts the webserver"""
        self.stop()
        self.start()

        # Reload components e.g. those in /plugins folder
        from trac.loader import load_components

        global_env = self.get_trac_environment()
        plugins_dir = global_env.shared_plugins_dir
        load_components(global_env, plugins_dir and (plugins_dir,))

    def product_testenv(self, product_id):
        if product_id == GLOBAL_ENV:
            return self.parent or self
        else:
            return FunctionalProductEnvironment(self, product_id)

    def product_environment(self, product_id):
        return ProductEnvironment(self.get_trac_environment(), product_id)

    def configure_web_hooks(self):
        """Setup web bootstrap_handlers and generation of product and global
        base URLs for a given user

        :return: a function used to generate base URL for product and
                 global environments . It will satisfy the following signature
                 `base_url(user=None, prefix=None, envname=None)` where::

                 @param user: username used to construct URLs for authenticated
                              requests
                 @param prefix: product prefix ; global environment selected
                                if missing
                 @param envname: environment name , useful in functional setup
                                 running sibling Trac environments under
                                 parent directory

        Generated URLs must be consistent with web hooks configuration
        @see: `_configure_web_hooks` method . By default `envname` is ignored
        and product base URL will be at /products under URL namespace of the
        global environment.
        """
        def _default_base_href(user=None, prefix=None, envname=None):
            if envname not in (self.bh_install_project, None):
                raise LookupError('Unknown environment ' + repr(envname))
            # TODO: Does not generate /login ? Should it ?
            parts = urllib2.urlparse.urlsplit(self.url)
            if not user or user == 'anonymous':
                global_href = Href('%s://%s/' % (parts[0], parts[1]))
            else:
                global_href = Href('%s://%s:%s@%s/' %
                                   (parts[0], user, user, parts[1]))
            # FIXME : Check that prefix is None is correct
            return global_href if (prefix is None or prefix == GLOBAL_ENV) \
                               else Href(global_href('products', prefix))

        return _default_base_href

    # Protected methods

    @property
    def _bloodhound_install_args(self):
        """Determine arguments supplied in to Bloodhound installer.
        """
        return dict(adminuser='admin', adminpass='admin',
                    dbstring=self.dburi, default_product_prefix='test',
                    digestfile=self.htdigest, realm=self.htdigest_realm,
                    repo_type=self.repotype,
                    repo_path=self.repo_path_for_initenv(),
                    sourcedir=self.bh_src)

    def _bloodhound_install(self):
        """Execute Bloodhound installer script
        """
        cwd = os.getcwdu()

        try:
            os.chdir(os.path.join(self.bh_src, 'installer'))
            create_digest = imp.load_source('bloodhound_setup',
                                            os.path.join(self.bh_src, 'installer',
                                                         'createdigest.py'))
            sys.modules['createdigest'] = create_digest
            bhsetup = imp.load_source('bloodhound_setup',
                                      os.path.join(self.bh_src, 'installer',
                                                   'bloodhound_setup.py'))

            # Enable timeline and roadmap views; needed in functional tests
            bhsetup.BASE_CONFIG['mainnav'].update({'timeline': 'enabled',
                                                   'roadmap': 'enabled'})

            bhsetup = bhsetup.BloodhoundSetup({'project' : self.bh_install_project,
                                               'envsdir' : self.dirname})

            # Do not perform Bloodhound-specific wiki upgrades
            bhsetup.apply_bhwiki_upgrades = False

            bh_install_args = self._bloodhound_install_args
            bhsetup.setup(**bh_install_args)
        except:
            raise
        else:
            self.bhmp_upgrade = True
        finally:
            os.chdir(cwd)

    def _fail_no_mp_setup(self):
        raise EnvironmentError('Product admin executed before upgrade')

    def _default_product(self, envname=None):
        """Default product configured for a given environment

        @raise LookupError: if no environment matching `envname` can be found
        """
        if envname not in ('trac', None):
            raise LookupError('Unable to open environment ' + envname)
        env = self.get_trac_environment()
        return MultiProductSystem(env).default_product_prefix


# TODO: Virtual ABCs for isinstance() checks
# TODO: Assess implications of forwarding methods to global test env
class FunctionalProductEnvironment(object):
    """Functional test environment limiting interactions to product context
    """
    def __init__(self, testenv, product_id):
        """Initialize functional product environment

        @param product_id: target product prefix
        @return: an object reusing resources in target functional test
                 environment to implement a compatible interface for
                 a given product environment
        @raise LookupError: if there's no product for given prefix
        """
        self.parent = testenv
        self.prefix = product_id
        self.url = self.parent.get_env_href(prefix=product_id)
        ProductEnvironment(testenv.get_trac_environment(), self.prefix)

    def _tracadmin(self, *args, **kwargs):
        """Execute trac-admin command in target product context by default
        """
        product_id = kwargs.get('product')
        if product_id is None:
            kwargs['product'] = self.prefix
        return self.parent._tracadmin(*args, **kwargs)

    def get_trac_environment(self):
        return ProductEnvironment(self.parent.get_trac_environment(),
                                  self.prefix)

    def create(self):
        raise RuntimeError('Bloodhound test environment already created')

    def _bloodhound_install(self):
        raise RuntimeError('Bloodhound test environment already created')

    def __getattr__(self, attrnm):
        try:
            if attrnm == 'parent':
                raise AttributeError
            return getattr(self.parent, attrnm)
        except AttributeError:
            raise AttributeError("'%s' object has no attribute '%s'" %
                                 (self.__class__.__name__, attrnm))


# TODO: Virtual ABCs for isinstance() checks
class BasicAuthTestEnvironment(object):
    """Setup tracd for HTTP basic authentication.
    """
    def _tracd_options(self):
        options = super(BasicAuthTestEnvironment, self)._tracd_options()
        options.append("--basic-auth=%s,%s," % (self.bh_install_project,
                                                self.htpasswd))
        return options


# TODO: Virtual ABCs for isinstance() checks
class DigestAuthTestEnvironment(object):
    """Setup tracd for HTTP digest authentication.
    """
    def _tracd_options(self):
        options = super(DigestAuthTestEnvironment, self)._tracd_options()
        options.append("--auth=%s,%s,%s" % (self.bh_install_project,
                                            self.htdigest,
                                            self.htdigest_realm))
        return options


class BloodhoundFunctionalTester(FunctionalTester):
    """Leverages Trac library of higher-level operations for interacting with
    a fully featured Apache(TM) Bloodhound test environment.

    Many things have changed in recent versions of Apache(TM) Bloodhound
    user interface once theme and dashboard are both installed:

    - 'New Ticket' link has been phased out in favor of 'More fields' link in
      quick create ticket shortcut menu.
    - New helper method `quick_create_ticket` has been added to create a
      new (random) ticket via quick create ticket shortcut menu.
    - 'logged in as user' label replaced by '<i class="icon-user"></i>user'
    - By using account manager plugin a web form must be submitted to login
    - As a consequence of default hooks new tickets in global scope are
      always bound to default product
    - Timeline module is disabled; frequently used along functional tests
    - View Tickets renamed to Tickets pointing at dashboard
    - Milestones `No date set` label replaced by `Unscheduled`
    - There's no actual button to submit `propertyform` in new ticket page
    - Different markup used to render ticket fields

    Other notable differences not solved by this class (target test cases
    should be rewritten?)

    - Preferences link removed in Bloodhound UI
    - There's no such thing like ticket preview in Bloodhound UI
    - 'Create New Ticket' label in new ticket page replaced by 'New Ticket'
    - Ticket owner label changed from 'Owned by' to 'Assigned to'
    - Source files (*.py) files copied in /plugins folder not enabled ootb
    - Twitter Bootstrap class="input-mini" added in 'Max items per page'
      input control in query view.
    - Ticket comment header changed
    - 'Page PageName created' is not shown anymore for new wiki page
    - Ticket workflow <select /> does not end with `id` attribute
    - Ticket events in timeline are different i.e. 'by user' outside <a />
    - Description 'modified' label in ticket comments feed inside <span />
    - closed: labels in milestone progress reports not shown anymore
    - active: labels in milestone progress reports not shown anymore
    - In ticket comments reply form 'Submit changes' => 'Submit'
    - No preview button for ticket (comments) in BH theme
    - class="input-mini" appended to priorities admin <select />

    As a consequence some methods of Trac functional tester have to be updated.
    """

    def __init__(self, url, skiplogin=False, instance_state=None):
        """Create a :class:`BloodhoundFunctionalTester` for the given
        environment URL and Subversion URL

        :param skiplogin:   Skip admin user login
        """
        self.url = url
        self._state = instance_state or dict(ticketcount={})

        # Connect, and login so we can run tests.
        self.go_to_front()
        if not skiplogin:
            self.login('admin')

    @property
    def ticketcount(self):
        """Retrieve ticket count from shared instance state.
        Ticket ID sequence is global.
        """
        ticketcount_cache = self._state.setdefault('ticketcount', {})
        return ticketcount_cache.get(self.url, 0)

    @ticketcount.setter
    def ticketcount(self, value):
        ticketcount_cache = self._state.setdefault('ticketcount', {})
        ticketcount_cache[self.url] = value

    def login(self, username):
        """Login as the given user

        Consider that 'logged in as user' label has been replaced by
        '<i class="icon-user"></i>user'
        """
        #FIXME: Keep/remove this ?
        #tc.add_auth("", self.url, username, username)
        self.go_to_front()
        tc.find("Login")
        tc.follow("Login")

        # Submit user + password via account manager login form
        tc.formvalue('acctmgr_loginform', 'user', username)
        tc.formvalue('acctmgr_loginform', 'password', username)
        tc.submit()
        self.go_to_front()

        tc.find(r'<i class="icon-user"></i>\s*%s' % username)
        tc.find("Logout")
        tc.url(self.url)
        tc.notfind(internal_error)

    def _post_create_ticket(self):
        """Look at the newly created ticket page after creating it
        """
        # we should be looking at the newly created ticket
        tc.url(self.url + '/ticket/%s' % (self.ticketcount + 1))
        # Increment self.ticketcount /after/ we've verified that the ticket
        # was created so a failure does not trigger spurious later
        # failures.
        self.ticketcount += 1

        # verify the ticket creation event shows up in the timeline
        self.go_to_timeline()
        tc.formvalue('prefs', 'ticket', True)
        tc.submit()
        tc.find('Ticket.*#%s.*created' % self.ticketcount)

    def create_ticket(self, summary=None, info=None):
        """Create a new (random) ticket in the test environment.  Returns
        the new ticket number.

        :param summary:
            may optionally be set to the desired summary
        :param info:
            may optionally be set to a dictionary of field value pairs for
            populating the ticket.  ``info['summary']`` overrides summary.

        `summary` and `description` default to randomly-generated values.
        """
        # [BLOODHOUND] New Ticket => More fields (in create ticket menu)
        self.go_to_newticket()

        tc.notfind(internal_error)
        if summary == None:
            summary = random_sentence(4)
        tc.formvalue('propertyform', 'field_summary', summary)
        tc.formvalue('propertyform', 'field_description', random_page())
        if info:
            for field, value in info.items():
                tc.formvalue('propertyform', 'field_%s' % field, value)

        # [BLOODHOUND] no actual button to submit /newticket `propertyform`
        tc.submit()

        self._post_create_ticket()
        return self.ticketcount

    def create_report(self, title, query, description):
        """Create a new report with the given title, query, and description
        """
        self.go_to_front()
        # [BLOODHOUND] View Tickets renamed to Tickets pointing at dashboard
        tc.follow(r'\bTickets\b')
        tc.notfind(internal_error)
        tc.follow(r'\bReports\b')
        tc.notfind(internal_error)
        tc.formvalue('create_report', 'action', 'new') # select new report form
        tc.submit()
        tc.find('New Report')
        tc.notfind(internal_error)
        tc.formvalue('edit_report', 'title', title)
        tc.formvalue('edit_report', 'description', description)
        tc.formvalue('edit_report', 'query', query)
        tc.submit()
        reportnum = b.get_url().split('/')[-1]
        # TODO: verify the url is correct
        # TODO: verify the report number is correct
        # TODO: verify the report does not cause an internal error
        # TODO: verify the title appears on the report list
        return reportnum

    def create_milestone(self, name=None, due=None):
        """Creates the specified milestone, with a random name if none is
        provided.  Returns the name of the milestone.
        """
        if name == None:
            name = random_unique_camel()
        milestone_url = self.url + "/admin/ticket/milestones"
        tc.go(milestone_url)
        tc.url(milestone_url)
        tc.formvalue('addmilestone', 'name', name)
        if due:
            # TODO: How should we deal with differences in date formats?
            tc.formvalue('addmilestone', 'duedate', due)
        tc.submit()
        tc.notfind(internal_error)
        tc.notfind('Milestone .* already exists')
        tc.url(milestone_url)
        tc.find(name)

        # Make sure it's on the roadmap.
        tc.follow('Roadmap')
        tc.url(self.url + "/roadmap")
        tc.find('Milestone:.*%s' % name)
        tc.follow(name)
        tc.url('%s/milestone/%s' % (self.url, unicode_quote(name)))
        if not due:
            # [BLOODHOUND] No date set => Unscheduled
            tc.find('Unscheduled')

        return name

    def go_to_query(self):
        """Surf to the custom query page.
        """
        self.go_to_front()
        # [BLOODHOUND] View Tickets (reports list) => Tickets (dashboard)
        tc.follow('^Tickets$')
        tc.notfind(internal_error)
        tc.url(self.url + '/dashboard')
        tc.follow('Custom Query')
        tc.url(self.url + '/query')

    def quickjump(self, search):
        """Do a quick search to jump to a page."""
        tc.formvalue('mainsearch', 'q', search)
        tc.submit()
        tc.notfind(internal_error)

    # Bloodhound functional tester extensions

    def go_to_newticket(self):
        self.go_to_front()

        tc.follow('More fields')

    def quick_create_ticket(self, summary=None, info=None):
        """Create a new (random) ticket in the test environment via quick
        create ticket shortcut. Returns the new ticket number.

        :param summary:
            may optionally be set to the desired summary
        :param info:
            may optionally be set to a dictionary of field value pairs for
            populating the ticket.  Fields are populated afterwards by
            navigating to ticket page, thereby ``info['summary']``overrides
            ``summary``.

        `summary` and `description` default to randomly-generated values.
        """
        self.go_to_front()
        tc.notfind(internal_error)

        if summary == None:
            summary = random_sentence(4)
        tc.formvalue('qct-form', 'field_summary', summary)
        tc.formvalue('qct-form', 'field_description', random_page())
        self._post_create_ticket()

        if info:
            # Second pass to update ticket fields
            tc.url(self.url + '/ticket/%s' % (self.ticketcount + 1))
            tc.notfind(internal_error)
            for field, value in info.items():
                tc.formvalue('inplace-propertyform', 'field_%s' % field, value)
            tc.submit('submit')

        return self.ticketcount

    @staticmethod
    def regex_ticket_field(fieldname, fieldval):
        return r'<td [^>]*\bid="vc-%s"[^>]*>\s*%s\s*</td>' % (fieldname, fieldval)

    @staticmethod
    def regex_owned_by(username):
        return '(Assigned to(<[^>]*>|\\n| )*%s)' % username

    @staticmethod
    def regex_query_column_selector(fieldname, fieldlbl):
        return r'<label>( |\n)*<input[^<]*value="%s"[^<]*/>' \
               r'( |\n)*<[^<]*>( |\n)*%s( |\n)*</[^<]*>' \
               r'( |\n)*</label>' % (fieldname, fieldlbl)

    def find_ticket_field(self, fieldname, fieldval):
        """Assert that expected value (pattern) matches value in ticket view
        """
        tc.find(self.regex_ticket_field(fieldname, fieldval))

    def find_owned_by(self, username):
        """Assert that a ticket is owned by a given user
        """
        tc.find(self.regex_owned_by(username))

    def find_query_column_selector(self, fieldname, fieldlbl):
        tc.find(self.regex_query_column_selector(fieldname, fieldlbl), 's')

    def as_user(self, user, restore='admin'):
        """Context manager to track access to the web site
        as user and restore login afterwards (by default to admin)
        """
        @contextlib.contextmanager
        def user_ctx():
            try:
                login_ok = False
                try:
                    self.logout()
                except:
                    pass
                if user:
                    self.login(user)
                    login_ok = True
                yield self
            finally:
                if login_ok:
                    try:
                        self.logout()
                    except:
                        pass
                if restore:
                    self.login(restore)

        return user_ctx()


    class in_product(object):
        """Context manager temporarily switching to product URL
        """
        def __init__(self, tester, url=None):
            self.tester = tester
            self.prev_url = None
            self.url = url

        def __enter__(self):
            """Replace tester base URL with default product's URL
            """
            self.prev_url = self.tester.url
            self.tester.url = self.url if self.url else \
                              getattr(self.tester, 'default_product_url',
                                      self.tester.url)
            return self.tester

        def __exit__(self, exc_type, exc_value, traceback):
            """Restore tester URL poiting at global environment
            """
            self.tester.url = self.prev_url

    def create_product(self, prefix=None, name=None, desc=None):
        """Create a product from the product list page."""
        products_url = self.url + '/products'
        tc.go(products_url)
        tc.find('Products')
        tc.submit('add', 'new')
        tc.find('New Product')

        prefix = prefix or random_word()
        name = name or random_sentence()
        desc = desc or random_paragraph()

        tc.formvalue('edit', 'prefix', prefix)
        tc.formvalue('edit', 'name', name)
        tc.formvalue('edit', 'description', desc)
        tc.submit()
        tc.find('The product "%s" has been added' % prefix)
        return prefix, name

    def admin_create_product(self, prefix=None, name=None, owner=None):
        """Create a product from the admin page."""
        admin_product_url = self.url + '/admin/ticket/products'
        tc.go(admin_product_url)
        tc.url(admin_product_url + '$')
        prefix = prefix or random_word()
        name = name or random_sentence()
        owner = owner or random_word()
        tc.formvalue('addproduct', 'prefix', prefix)
        tc.formvalue('addproduct', 'name', name)
        tc.formvalue('addproduct', 'owner', owner)
        tc.submit()

        tc.find(r'The product "%s" has been added' % prefix)
        tc.find(r'<a href="/admin/ticket/products/%s">%s</a>'
                % (prefix, prefix))
        tc.find(r'<a href="/admin/ticket/products/%s">%s</a>'
                % (prefix, name))
        tc.find(r'<td class="owner">%s</td>' % owner)
        return prefix, name, owner

    def go_to_dashboard(self):
        """Surf to the dashboard page."""
        self.go_to_front()
        tc.follow('Tickets')
        tc.url(self.url + '/dashboard')


class BloodhoundGlobalEnvFunctionalTester(BloodhoundFunctionalTester):
    """Library of higher-level operations for interacting with
    a global Apache(TM) Bloodhound test environment enabled with automatic
    redirects from global environment to resources in default product.

    Many things have changed in recent versions of Apache(TM) Bloodhound
    user interface once theme and dashboard are both installed. Beyond common
    differences this functional tester also deals with :

    - Tickets are created in default product context
    - Admin panels for ticket fields are only accessible in default product
      context
    - Reports are created in default product context

    As a consequence some methods of Trac functional tester have to be
    executed in special ways.
    """
    def __init__(self, url, *args, **kwargs):
        super(BloodhoundGlobalEnvFunctionalTester,
              self).__init__(url, *args, **kwargs)
        self.default_product_url = None

    class in_product(BloodhoundFunctionalTester.in_product):
        """Context manager temporarily switching to product URL
        """
        def __init__(self, tester, url=None):
            if url is not None and \
                    isinstance(tester, BloodhoundGlobalEnvFunctionalTester):
                # Create a regular functional tester instance, no redirections
                default_product_url = tester.default_product_url
                tester = BloodhoundFunctionalTester(tester.url, True,
                                                    tester._state)
                tester.default_product_url = default_product_url
            super(self.__class__, self).__init__(tester, url)

    def _post_create_ticket(self):
        """Look at the newly created ticket page after creating it
        ... but in default product context ...
        """
        superobj = super(BloodhoundGlobalEnvFunctionalTester, self)
        with self.in_product(self):
            return superobj._post_create_ticket()

    def create_milestone(self, name=None, due=None):
        """Creates the specified milestone, with a random name if none is
        provided.  Returns the name of the milestone.

        ... executed in default product context
        """
        superobj = super(BloodhoundGlobalEnvFunctionalTester, self)
        with self.in_product(self):
            return superobj.create_milestone(name, due)

    def create_component(self, name=None, user=None):
        """Creates the specified component, with a random camel-cased name if
        none is provided.  Returns the name.

        ... executed in default product context
        """
        superobj = super(BloodhoundGlobalEnvFunctionalTester, self)
        with self.in_product(self):
            return superobj.create_component(name, user)

    def create_enum(self, kind, name=None):
        """Helper to create the specified enum (used for ``priority``,
        ``severity``, etc). If no name is given, a unique random word is used.
        The name is returned.

        ... executed in default product context

        """
        superobj = super(BloodhoundGlobalEnvFunctionalTester, self)
        with self.in_product(self):
            return superobj.create_enum(kind, name)

    def create_version(self, name=None, releasetime=None):
        """Create a new version.  The name defaults to a random camel-cased
        word if not provided.

        ... executed in default product context
        """
        superobj = super(BloodhoundGlobalEnvFunctionalTester, self)
        with self.in_product(self):
            return superobj.create_version(name, releasetime)


class OpenerDirectorMixin(object):
    """URL opener extensions for functional testers.
    """
    def build_opener(self, url, user, passwd=None):
        """Build an urllib2 OpenerDirector configured to access the web
        instance on behalf of a given user
        """
        return urllib2.build_opener()


class HttpAuthTester(OpenerDirectorMixin):
    """Configure HTTP authentication (basic or digest, proxy, ...)
    """

    def url_auth_handlers(self, password_mgr):
        """Return a (list of) instance(s) of urllib2.AbstractBasicAuthHandler,
        urllib2.AbstractDigestAuthHandler or equivalent.
        """
        raise NotImplementedError("Must override 'url_auth_handlers' method")

    def build_opener(self, url, user, passwd=None):
        password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        handlers = self.url_auth_handlers(password_mgr)
        if not isinstance(handlers, (tuple, list)):
            handlers = (handlers,)
        password_mgr.add_password(realm=None, uri=url, user=user,
                                  passwd=passwd or user)
        return urllib2.build_opener(*handlers)


#----------------
# Twill's find command accepts regexes; some convenient but complex regexes
# & regex factories are provided here :
#----------------

regex_owned_by = BloodhoundFunctionalTester.regex_owned_by
regex_ticket_field = BloodhoundFunctionalTester.regex_ticket_field

#----------------
# Product-aware functional setup
#----------------

class MultiproductFunctionalTestSuite(functional.FunctionalTestSuite):
    """TestSuite that leverages a test fixture containing a
    FunctionalTestEnvironment and a FunctionalTester by also
    upgrading them to multi-product support after activating Bloodhound theme
    and dashboard plugins.
    """

    class env_class(MultiproductFunctionalMixin,
                    functional.FunctionalTestSuite.env_class):
        pass

    tester_class = BloodhoundGlobalEnvFunctionalTester

    def testenv_path(self, port=None):
        if port is None:
            dirname = "testenv"
        else:
            dirname = "testenv%s" % port
        return os.path.join(functional.trac_source_tree, dirname)

    def setUp(self, port=None):
        print "Starting web server ..."
        try:
            # Rewrite FunctionalTestSuite.setUp for custom dirname
            dirname = self.testenv_path(port)
            if port is None:
                port = 8000 + os.getpid() % 1000

            baseurl = "http://127.0.0.1:%s" % port
            self._testenv = self.env_class(dirname, port, baseurl)
            self._testenv.start()
            self._tester = self.tester_class(baseurl)
            self.fixture = (self._testenv, self._tester)
        except:
            # Ensure tracd process is killed on failure
            print "Stopping web server...\n"
            testenv = getattr(self, '_testenv', None)
            if testenv:
                testenv.stop()
            raise
        else:
            prefix = self._testenv._default_product()
            default_product_base = self._testenv.get_env_href(user=None,
                                                              prefix=prefix)
            self._tester.default_product_url = default_product_base()
            print "Started web server: %s" % self._testenv.url

    def run(self, result):
        """Setup the fixture (self.setUp), call .setFixture on all the tests,
        and tear down the fixture (self.tearDown).

        Ensure marked tests will be wrapped by specialized context manager in
        order access default product URL namespace instead of global.
        """
        self.setUp()
        # FIXME: Loop once over test cases
        if hasattr(self, 'fixture'):
            for test in self._tests:
                if hasattr(test, 'setFixture'):
                    test.setFixture(self.fixture)
        # Override unittest loop
        for test in self._tests:
            if result.shouldStop:
                break
            if getattr(test, 'BH_IN_DEFAULT_PRODUCT', False):
                if hasattr(test, 'in_product'):
                    with test.in_product():
                        test(result)
                elif hasattr(self._tester, 'in_product'):
                    with self._tester.in_product(self._tester):
                        test(result)
                else:
                    try:
                        raise RuntimeError('Impossible to run test %s in '
                                           'default product' % (test,))
                    except:
                        err = sys.exc_info()
                    result.addError(test, err)
            else:
                test(result)
        self.tearDown()
        return result

    def tearDown(self):
        print "\nStopping web server...\n"
        functional.FunctionalTestSuite.tearDown(self)

class MultiproductFunctionalTestCase(object):
    """Mixin extending functional test case setup classes with multi-product
    test methods.
    """
    def in_product(self, prefix=None):
        """Switch the functional tester to work in product context.

        :param prefix:  target product prefix
        :return:        context manager object
        """
        # Force setting tester and test environment
        functional.FunctionalTestCaseSetup.setUp(self)

        @contextlib.contextmanager
        def in_product_testenv(product_id):
            try:
                # Backup active test env
                original = self._testenv
                self._testenv = original.product_testenv(product_id)
                yield self._testenv
            finally:
                self._testenv = original

        if prefix is None:
            default_product = self._testenv._default_product()
            return contextlib.nested(in_product_testenv(default_product),
                                     self._tester.in_product(self._tester))
        else:
            product_href = self._testenv.get_env_href(prefix=prefix)
            return contextlib.nested(in_product_testenv(prefix),
                          self._tester.in_product(self._tester, product_href()))

# Mark some test cases to be run against default product
import trac.ticket.tests.functional
import trac.admin.tests.functional
from trac.tests.functional import testcases

ignore_tc = (functional.FunctionalTwillTestCaseSetup,
             functional.FunctionalTestCaseSetup)
for mdl in (trac.ticket.tests.functional, trac.admin.tests.functional):
    for attr in dir(mdl):
        attr = getattr(mdl, attr)
        if isclass(attr) and attr not in ignore_tc \
                and issubclass(attr, functional.FunctionalTestCaseSetup):
            attr.BH_IN_DEFAULT_PRODUCT = True
del attr, mdl, ignore_tc

testcases.RegressionTestTicket7209.BH_IN_DEFAULT_PRODUCT = True
testcases.RegressionTestTicket9880.BH_IN_DEFAULT_PRODUCT = True


def trac_functionalSuite(suite):
    from trac.tests.functional import testcases
    suite.addTest(testcases.RegressionTestRev6017())
    suite.addTest(testcases.RegressionTestTicket3833a())
    suite.addTest(testcases.RegressionTestTicket3833b())
    suite.addTest(testcases.RegressionTestTicket3833c())
    suite.addTest(testcases.RegressionTestTicket5572())
    suite.addTest(testcases.RegressionTestTicket7209())
    suite.addTest(testcases.RegressionTestTicket9880())
    suite.addTest(testcases.ErrorPageValidation())
    suite.addTest(testcases.RegressionTestTicket3663())

    import trac.admin.tests
    trac.admin.tests.functionalSuite(suite)
    import trac.versioncontrol.tests
    trac.versioncontrol.tests.functionalSuite(suite)
    import trac.wiki.tests
    trac.wiki.tests.functionalSuite(suite)
    import trac.timeline.tests
    trac.timeline.tests.functionalSuite(suite)

    # import trac.ticket.tests
    # trac.ticket.tests.functionalSuite(suite)
    import tests.functional.ticket
    tests.functional.ticket.functionalSuite(suite)

    # import trac.prefs.tests
    # trac.prefs.tests.functionalSuite(suite)
    import tests.functional.prefs
    tests.functional.prefs.functionalSuite(suite)

    import tests.functional.product
    tests.functional.product.functionalSuite(suite)

    # The db tests should be last since the backup test occurs there.
    import trac.db.tests
    trac.db.tests.functionalSuite(suite)


def functionalSuite():
    suite = MultiproductFunctionalTestSuite()
    return suite


def test_suite():
    suite = functionalSuite()

    #from tests import TestLoader
    # FIXME: Does this work for functional tests suite ?
    # bhsuite = TestLoader().discover_package('tests.functional', pattern='*.py')

    trac_functionalSuite(suite)

    import tests.functional.admin
    tests.functional.admin.functionalSuite(suite)

    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
