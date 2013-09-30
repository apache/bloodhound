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

import imp
from inspect import isclass
import os
from subprocess import call, Popen
import sys
import time
import urllib
import urllib2

from trac.tests.contentgen import random_sentence, random_page,\
    random_unique_camel
from trac.tests import functional
from trac.tests.functional.svntestenv import SvnFunctionalTestEnvironment
from trac.tests.functional.testenv import FunctionalTestEnvironment, ConnectError
from trac.tests.functional.tester import b, FunctionalTester, internal_error, tc
from trac.util.compat import close_fds
from trac.util.text import unicode_quote
from trac.web.href import Href
from multiproduct.api import MultiProductSystem
from multiproduct import hooks

from tests import unittest

#----------------
# Product-aware classes for functional tests
#----------------

class MultiproductFunctionalMixin(object):
    """Mixin class applying multi-product upgrade path upon a given
    functional Trac test environment. Access to the global environment
    is provided at testing time. In order to obtain a compatible test
    environment for a given product @see: `product_test_env` method 

    @attention: This class must precede functional test environment class in
                class declaration because it overrides some methods
    """

    def init(self):
        """Determine the location of Trac source code
        """
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
        if envname not in ('trac', None):
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
        if product_id:
            if self.bhmp_upgrade and \
                    args[0] not in ProductAdminModule.GLOBAL_COMMANDS:
                args = ('product', 'admin', product_id) + args
            elif not self.bhmp_upgrade:
                self._fail_no_mp_setup()

        super(MultiproductFunctionalMixin, self)._tracadmin(*args, **kwargs)
        if do_wait: # Delay to ensure command executes and caches resets
            time.sleep(5)

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
        options = ["--port=%s" % self.port, "-s", "--hostname=127.0.0.1"]
        if 'TRAC_TEST_TRACD_OPTIONS' in os.environ:
            options += os.environ['TRAC_TEST_TRACD_OPTIONS'].split()
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

    def product_test_env(self, product_id):
        """Functional test environment for product

        @param product_id: target product prefix
        @return: an object reusing resources in target functional test
                 environment to implement a compatible interface for
                 a given product environment
        @raise LookupError: if there's no product for given prefix
        """
        raise NotImplementedError()

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
            # TODO: Does not generate /login ? Should it ?
            parts = urllib2.urlparse.urlsplit(self.url)
            if not user or user == 'anonymous':
                global_href = Href('%s://%s/' % (parts[0], parts[1]))
            else:
                global_href = Href('%s://%s:%s@%s/' % 
                                   (parts[0], user, user, parts[1]))
            return global_href if not prefix \
                               else Href(global_href('products', prefix))

        return _default_base_href

    # Protected methods

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

            #FIXME: Account manager's store will not work even after this
            # Prepare installer for HTTP basic authentication store
#            bhsetup.ACCOUNTS_CONFIG['account-manager'].update(
#                          {'htpasswd_file' : self.htpasswd,
#                           'password_store' : 'HtPasswdStore'})

            # Enable timeline and roadmap views; needed in functional tests
            bhsetup.BASE_CONFIG['mainnav'].update({'timeline': 'enabled',
                                                   'roadmap': 'enabled'})

            bhsetup = bhsetup.BloodhoundSetup({'project' : 'trac',
                                               'envsdir' : self.dirname})

            # Do not perform Bloodhound-specific wiki upgrades
            bhsetup.apply_bhwiki_upgrades = False

            bhsetup.setup(adminuser='admin', adminpass='admin', 
                          dbstring=self.dburi, default_product_prefix='test',
                          digestfile=self.htdigest, realm=self.htdigest_realm,
                          repo_type=self.repotype,
                          repo_path=self.repo_path_for_initenv(),
                          sourcedir=self.bh_src)

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

    As a consequence some methods of Trac functional tester have to be updated.
    """

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
        tc.follow('Tickets')
        tc.notfind(internal_error)
        tc.follow('Reports')
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

    def find_ticket_field(self, fieldname, fieldval):
        """Assert that expected value (pattern) matches value in ticket view
        """
        tc.find(r'<td [^>]*\bid="vc-%s"[^>]*>\s*%s\s*</td>' % (fieldname, fieldval))


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
    def __init__(self, url, default_product_url=None):
        super(BloodhoundGlobalEnvFunctionalTester, self).__init__(url)
        self.default_product_url = default_product_url

    class in_defaut_product(object):
        """Context manager temporarily switching to default product URL
        """
        def __init__(self, tester):
            self.tester = tester
            self.global_url = None

        def __enter__(self):
            """Replace tester base URL with default product's URL
            """
            self.global_url = self.tester.url
            self.tester.url = self.tester.default_product_url
            return self.tester

        def __exit__(self, exc_type, exc_value, traceback):
            """Restore tester URL poiting at global environment
            """
            self.tester.url = self.global_url 

    def _post_create_ticket(self):
        """Look at the newly created ticket page after creating it
        ... but in default product context ...
        """
        superobj = super(BloodhoundGlobalEnvFunctionalTester, self)
        with self.in_defaut_product(self):
            return superobj._post_create_ticket()

    def create_milestone(self, name=None, due=None):
        """Creates the specified milestone, with a random name if none is
        provided.  Returns the name of the milestone.

        ... executed in default product context 
        """
        superobj = super(BloodhoundGlobalEnvFunctionalTester, self)
        with self.in_defaut_product(self):
            return superobj.create_milestone(name, due)

    def create_component(self, name=None, user=None):
        """Creates the specified component, with a random camel-cased name if
        none is provided.  Returns the name.

        ... executed in default product context 
        """
        superobj = super(BloodhoundGlobalEnvFunctionalTester, self)
        with self.in_defaut_product(self):
            return superobj.create_component(name, user)

    def create_enum(self, kind, name=None):
        """Helper to create the specified enum (used for ``priority``,
        ``severity``, etc). If no name is given, a unique random word is used.
        The name is returned.

        ... executed in default product context 

        """
        superobj = super(BloodhoundGlobalEnvFunctionalTester, self)
        with self.in_defaut_product(self):
            return superobj.create_enum(kind, name)

    def create_version(self, name=None, releasetime=None):
        """Create a new version.  The name defaults to a random camel-cased
        word if not provided.

        ... executed in default product context 
        """
        superobj = super(BloodhoundGlobalEnvFunctionalTester, self)
        with self.in_defaut_product(self):
            return superobj.create_version(name, releasetime)


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

    def setUp(self, port=None):
        print "Starting web server ..."
        try:
            functional.FunctionalTestSuite.setUp(self)
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
        if hasattr(self, 'fixture'):
            for test in self._tests:
                if hasattr(test, 'setFixture'):
                    test.setFixture(self.fixture)
        # Override unittest loop
        for test in self._tests:
            if result.shouldStop:
                break
            if getattr(test, 'BH_IN_DEFAULT_PRODUCT', False) and \
                    hasattr(self._tester, 'in_defaut_product'):
                with self._tester.in_defaut_product(self._tester):
                    test(result)
            else:
                test(result)
        self.tearDown()
        return result

    def tearDown(self):
        print "\nStopping web server...\n"
        functional.FunctionalTestSuite.tearDown(self)

# Mark some test cases to be run against default product
import trac.ticket.tests.functional
import trac.admin.tests.functional
for mdl in (trac.ticket.tests.functional, trac.admin.tests.functional):
    for attr in dir(mdl):
        attr = getattr(mdl, attr)
        if isclass(attr) and issubclass(attr, 
                                        functional.FunctionalTwillTestCaseSetup):
            attr.BH_IN_DEFAULT_PRODUCT = True
del attr, mdl

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

    import trac.versioncontrol.tests
    trac.versioncontrol.tests.functionalSuite(suite)

    # import trac.ticket.tests
    # trac.ticket.tests.functionalSuite(suite)
    import tests.functional.ticket
    tests.functional.ticket.functionalSuite(suite)

    # import trac.prefs.tests
    # trac.prefs.tests.functionalSuite(suite)
    import tests.functional.prefs
    tests.functional.prefs.functionalSuite(suite)

    import trac.wiki.tests
    trac.wiki.tests.functionalSuite(suite)
    import trac.timeline.tests
    trac.timeline.tests.functionalSuite(suite)
    import trac.admin.tests
    trac.admin.tests.functionalSuite(suite)
    # The db tests should be last since the backup test occurs there.
    import trac.db.tests
    trac.db.tests.functionalSuite(suite)


def functionalSuite():
    suite = MultiproductFunctionalTestSuite()
    return suite


def test_suite():
    suite = functionalSuite()

    # TODO: Load Bloodhound-specific functional test cases

    #from tests import TestLoader
    # FIXME: Does this work for functional tests suite ?
    # bhsuite = TestLoader().discover_package('tests.functional', pattern='*.py')

    trac_functionalSuite(suite)

    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
