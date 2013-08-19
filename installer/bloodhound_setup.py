#!/usr/bin/env python

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
"""Initial configuration for Bloodhound"""

import os
import pkg_resources
import sys
import traceback

import ConfigParser
from getpass import getpass
from optparse import OptionParser
import shutil
import time

from createdigest import htdigest_create

from trac.util import translation
from trac.util.translation import _, get_negotiated_locale, has_babel
LANG = os.environ.get('LANG')

try:
    from trac.admin.console import TracAdmin
    from trac.config import Configuration
except ImportError, e:
    print ("Post install setup requires that Bloodhound is properly installed "
           "Traceback for error follows:\n")
    traceback.print_exc()
    sys.exit(1)

try:
    import psycopg2
except ImportError:
    psycopg2 = None

MAXBACKUPNUMBER = 64  # Max attempts to create backup file

DEFAULT_DB_USER = 'bloodhound'
DEFAULT_DB_NAME = 'bloodhound'
DEFAULT_ADMIN_USER = 'admin'

BH_PROJECT_SITE = 'https://issues.apache.org/bloodhound/'
BASE_CONFIG = {'components': {'bhtheme.*': 'enabled',
                              'bhdashboard.*': 'enabled',
                              'multiproduct.*': 'enabled',
                              'permredirect.*': 'enabled',
                              'themeengine.api.*': 'enabled',
                              'themeengine.web_ui.*': 'enabled',
                              'bhsearch.*': 'enabled',
                              'bhrelations.*': 'enabled',
                              'trac.ticket.web_ui.ticketmodule': 'disabled',
                              'trac.ticket.report.reportmodule': 'disabled',
                              },
               'header_logo': {'src': '',},
               'mainnav': {'roadmap': 'disabled',
                           'search': 'disabled',
                           'timeline': 'disabled',
                           'browser.label': 'Source',
                           'tickets.label': 'Tickets',},
               'metanav': {'about': 'disabled',},
               'theme': {'theme': 'bloodhound',},
               'trac': {'mainnav': ','.join(['dashboard', 'wiki', 'browser',
                                             'tickets', 'newticket', 'timeline',
                                             'roadmap', 'search', 'admin']),
                        'environment_factory': '',
                        'request_factory': '',},
               'project': {'footer': ('Get involved with '
                                      '<a href="%(site)s">Apache Bloodhound</a>'
                                      % {'site': BH_PROJECT_SITE,}),},
               'labels': {'application_short': 'Bloodhound',
                          'application_full': 'Apache Bloodhound',
                          'footer_left_prefix': '',
                          'footer_left_postfix': '',
                          'footer_right': ''},
               'bhsearch': {'is_default': 'true', 'enable_redirect': 'true'},
}

ACCOUNTS_CONFIG = {'account-manager': {'account_changes_notify_addresses' : '',
                                       'authentication_url' : '',
                                       'db_htdigest_realm' : '',
                                       'force_passwd_change' :'true',
                                       'hash_method' : 'HtDigestHashMethod',
                                       'htdigest_file' : '',
                                       'htdigest_realm' : '',
                                       'htpasswd_file' : '',
                                       'htpasswd_hash_type' : 'crypt',
                                       'password_store' : 'HtDigestStore',
                                       'persistent_sessions' : 'False',
                                       'refresh_passwd' : 'False',
                                       'user_lock_max_time' : '0',
                                       'verify_email' : 'True',
                                       },
                   'components': {'acct_mgr.admin.*' : 'enabled',
                                  'acct_mgr.api.accountmanager' : 'enabled',
                                  'acct_mgr.guard.accountguard' : 'enabled',
                                  'acct_mgr.htfile.htdigeststore' : 'enabled',
                                  'acct_mgr.macros.*': 'enabled',
                                  'acct_mgr.web_ui.accountmodule' : 'enabled',
                                  'acct_mgr.web_ui.loginmodule' : 'enabled',
                                  'trac.web.auth.loginmodule' : 'disabled',
                                  },
                   }

class BloodhoundSetup(object):
    """Creates a Bloodhound environment"""

    def __init__(self, opts):
        if isinstance(opts, dict):
            options = dict(opts)
        else:
            options = vars(opts)
        self.options = options

        if 'project' not in options:
            options['project'] = 'main'
        if 'envsdir' not in options:
            options['envsdir'] = os.path.join('bloodhound',
                                              'environments')

    def _generate_db_str(self, options):
        """Builds an appropriate db string for trac-admin for sqlite and
        postgres options. Also allows for a user to provide their own db string
        to allow database initialisation beyond these."""
        dbdata = {'user': options.get('dbuser'),
                  'pass': options.get('dbpass'),
                  'host': options.get('dbhost', 'localhost'),
                  'port': options.get('dbport', '5432'),
                  'name': options.get('dbname', 'bloodhound'),
                  }

        db = options.get('dbstring')
        if db is None:
            dbtype = options.get('dbtype', 'sqlite')
            if (dbtype == 'postgres' and dbdata['user'] is not None
                                     and dbdata['pass'] is not None):
                db = 'postgres://%(user)s:%(pass)s@%(host)s:%(port)s/%(name)s'
            else:
                db = 'sqlite:%s' % os.path.join('db', '%(name)s.db')
        return db % dbdata

    def setup(self, **kwargs):
        """Do the setup. A kwargs dictionary may be passed to override base
        options, potentially allowing for multiple environment creation."""
        
        if has_babel:
            import babel
            try:
                locale = get_negotiated_locale([LANG]) 
                locale = locale or babel.Locale.default()
            except babel.UnknownLocaleError:
                pass
            translation.activate(locale)
        
        options = dict(self.options)
        options.update(kwargs)
        if psycopg2 is None and options.get('dbtype') == 'postgres':
            print "psycopg2 needs to be installed to initialise a postgresql db"
            return False

        environments_path = options['envsdir']
        if not os.path.exists(environments_path):
            os.makedirs(environments_path)

        new_env =  os.path.join(environments_path, options['project'])
        tracini = os.path.abspath(os.path.join(new_env, 'conf', 'trac.ini'))
        baseini = os.path.abspath(os.path.join(new_env, 'conf', 'base.ini'))
        options['inherit'] = '"' + baseini + '"'

        options['db'] = self._generate_db_str(options)
        if 'repo_type' not in options or options['repo_type'] is None:
            options['repo_type'] = ''
        if 'repo_path' not in options or options['repo_path'] is None:
            options['repo_path'] = ''
        if (len(options['repo_type']) > 0) ^ (len(options['repo_path']) > 0):
            print "Error: Specifying a repository requires both the "\
                  "repository-type and the repository-path options."
            return False

        custom_prefix = 'default_product_prefix'
        if custom_prefix in options and options[custom_prefix]:
            default_product_prefix = options[custom_prefix]
        else:
            default_product_prefix = '@'

        digestfile = os.path.abspath(os.path.join(new_env,
                                                  options['digestfile']))
        realm =  options['realm']
        adminuser = options['adminuser']
        adminpass = options['adminpass']

        # create base options:
        accounts_config = dict(ACCOUNTS_CONFIG)
        accounts_config['account-manager']['htdigest_file'] = digestfile
        accounts_config['account-manager']['htdigest_realm'] = realm

        trac = TracAdmin(os.path.abspath(new_env))
        if not trac.env_check():
            try:
                trac.do_initenv('%(project)s %(db)s '
                                '%(repo_type)s %(repo_path)s '
                                '--inherit=%(inherit)s '
                                '--nowiki'
                                % options)
            except SystemExit:
                print ("Error: Unable to initialise the database"
                       "Traceback for error is above")
                return False
        else:
            print ("Warning: Environment already exists at %s." % new_env)
            self.writeconfig(tracini, [{'inherit': {'file': baseini},},])

        base_config = dict(BASE_CONFIG)
        environment_factory_path = os.path.abspath(
                                      os.path.normpath(
                                          os.path.join(options['sourcedir'],
                                                               'bloodhound_multiproduct/multiproduct/hooks.py')))
        request_factory_path = os.path.abspath(
                                   os.path.normpath(
                                       os.path.join(options['sourcedir'],
                                                            'bloodhound_multiproduct/multiproduct/hooks.py')))
        base_config['trac']['environment_factory'] = environment_factory_path
        base_config['trac']['request_factory'] = request_factory_path
        if default_product_prefix != '@':
            base_config['multiproduct'] = dict(
                default_product_prefix=default_product_prefix
            )

        self.writeconfig(baseini, [base_config, accounts_config])

        if os.path.exists(digestfile):
            backupfile(digestfile)
        htdigest_create(digestfile, adminuser, realm, adminpass)

        print "Adding TRAC_ADMIN permissions to the admin user %s" % adminuser
        trac.onecmd('permission add %s TRAC_ADMIN' % adminuser)

        # get fresh TracAdmin instance (original does not know about base.ini)
        bloodhound = TracAdmin(os.path.abspath(new_env))

        # final upgrade
        print "Running upgrades"
        bloodhound.onecmd('upgrade')
        pages = []
        pages.append(pkg_resources.resource_filename('bhdashboard',
                                                 'default-pages'))
        pages.append(pkg_resources.resource_filename('bhsearch',
                                                 'default-pages'))
        bloodhound.onecmd('wiki load %s' % " ".join(pages))

        print "Running wiki upgrades"
        bloodhound.onecmd('wiki upgrade')
        
        print "Running wiki Bloodhound upgrades"
        bloodhound.onecmd('wiki bh-upgrade')

        print "Loading default product wiki"
        bloodhound.onecmd('product admin %s wiki load %s' %
                          (default_product_prefix,
                           " ".join(pages)))

        print "Running default product wiki upgrades"
        bloodhound.onecmd('product admin %s wiki upgrade' %
                          default_product_prefix)

        print "Running default product wiki Bloodhound upgrades"
        bloodhound.onecmd('product admin %s wiki bh-upgrade' %
                          default_product_prefix)

        print """
You can now start Bloodhound by running:

  tracd --port=8000 %s

And point your browser at http://localhost:8000/%s
""" % (os.path.abspath(new_env), options['project'])
        return True

    def writeconfig(self, filepath, dicts=[]):
        """Writes or updates a config file. A list of dictionaries is used so
        that options for different aspects of the configuration can be kept
        separate while being able to update the same sections. Note that the
        result is order dependent where two dictionaries update the same option.
        """
        config = Configuration(filepath)
        file_changed = False
        for data in dicts:
            for section, options in data.iteritems():
                for key, value in options.iteritems():
                    if config.get(section, key, None) != value:
                        # This should be expected to generate a false positive
                        # when two dictionaries update the same option
                        file_changed = True
                    config.set(section, key, value)
        if file_changed:
            if os.path.exists(filepath):
                backupfile(filepath)
            config.save()

def backupfile(filepath):
    """Very basic backup routine"""
    print "Warning: Updating %s." % filepath
    backuppath = None
    if not os.path.exists(filepath + '_bak'):
        backuppath = filepath + '_bak'
    else:
        backuptemplate = filepath + '_bak_%d'
        for i in xrange(MAXBACKUPNUMBER):
            if not os.path.exists(backuptemplate % i):
                backuppath = backuptemplate % i
                break
    if backuppath is not None:
        shutil.copyfile(filepath, backuppath)
        print "Backup created at %s." % backuppath
    else:
        print "No backup created (too many other backups found)"
    return backuppath

def handle_options():
    """Parses the command line, with basic prompting for choices where options
    are not specified."""
    parser = OptionParser()

    # Base Trac Options
    parser.add_option('--project', dest='project',
                      help='Set the top project name', default='main')
    parser.add_option('--source_directory', dest='sourcedir',
                      help='Specify root source code directory',
                      default=os.path.normpath(os.path.join(os.getcwd(), '../'))),
    parser.add_option('--environments_directory', dest='envsdir',
                      help='Set the directory to contain environments',
                      default=os.path.join('bloodhound', 'environments'))
    parser.add_option('-d', '--database-type', dest='dbtype',
                      help="Specify as either 'postgres' or 'sqlite'",
                      default='')
    parser.add_option('--database-string', dest='dbstring',
                      help=('Advanced: provide a custom database string, '
                            'overriding other database options'),
                      default=None)
    parser.add_option('--database-name', dest='dbname',
                      help='Specify the database name',
                      default='bloodhound')
    parser.add_option('-u', '--user', dest='dbuser',
                      help='Specify the db user (required for postgres)',
                      default='')
    parser.add_option('-p', '--password', dest='dbpass',
                      help='Specify the db password (option for postgres)')
    parser.add_option('--database-host', dest='dbhost',
                      help='Specify the database host (optional for postgres)',
                      default='localhost')
    parser.add_option('--database-port', dest='dbport',
                      help='Specify the database port (optional for postgres)',
                      default='5432')

    # Account Manager Options
    parser.add_option('--admin-password', dest='adminpass',
                      help='create an admin user in an htdigest file')
    parser.add_option('--digest-realm', dest='realm', default='bloodhound',
                      help='authentication realm for htdigest file')
    parser.add_option('--admin-user', dest='adminuser', default='',
                      help='admin user name for htdigest file')
    parser.add_option('--digest-file', dest='digestfile',
                      default='bloodhound.htdigest',
                      help='filename for the htdigest file')

    # Repository Options
    parser.add_option('--repository-type', dest='repo_type',
                      help='specify the repository type - ')
    parser.add_option('--repository-path', dest='repo_path',
                      help='specify the repository type')

    # Multiproduct options
    parser.add_option('--default-product-prefix', dest='default_product_prefix',
                      help='Specify prefix for default product (defaults to @')

    (options, args) = parser.parse_args()
    if args:
        print "Unprocessed options/arguments: ", args

    def ask_question(question, default=None):
        """Basic question asking functionality"""
        if default:
            answer = raw_input(question % default)
        else:
            answer = raw_input(question)
        return answer if answer else default

    def ask_password(user):
        """Asks for a password to be provided for setting purposes"""
        attempts = 3
        for attempt in range(attempts):
            if attempt > 0:
                print "Passwords empty or did not match. Please try again",
                print "(attempt %d/%d)""" % (attempt+1, attempts)
            password1 = getpass('Enter a new password for "%s": ' % user)
            password2 = getpass('Please reenter the password: ')
            if password1 and password1 == password2:
                return password1
        print "Passwords did not match. Quitting."
        sys.exit(1)

    if options.dbtype.lower() not in ['postgres','sqlite']:
        answer = ask_question('''
This installer is able to install Apache Bloodhound with either SQLite or
PostgreSQL databases. SQLite is an easier option for installing Bloodhound as
SQLite is usually built into Python and also requires no special permissions to
run. However, PostgreSQL is generally expected to be more robust for production
use.
Do you want to install to a PostgreSQL database [%s]: ''', default='Y/n')
        answer = answer.lower()
        options.dbtype = 'postgres' if answer not in ['n','no'] else 'sqlite'
    else:
        options.dbtype = options.dbtype.lower()

    if options.dbtype == 'postgres':
        if not options.dbuser:
            options.dbuser = ask_question("""
For PostgreSQL you need to have PostgreSQL installed and you need to have
created a database user to connect to the database with. Setting this up may
require admin access rights to the server.
DB user name [%s]: """, DEFAULT_DB_USER)

        if not options.dbpass:
            options.dbpass = ask_password(options.dbuser)

        if not options.dbname:
            options.dbname = ask_question("""
For PostgreSQL setup, you need to specify a database that you have created for
Bloodhound to use. This installer currently assumes that this database will be
empty.
DB name [%s]: """, DEFAULT_DB_NAME)
    if not options.adminuser:
        options.adminuser = ask_question("""
Please supply a username for the admin user [%s]: """, DEFAULT_ADMIN_USER)
    if not options.adminpass:
        options.adminpass = ask_password(options.adminuser)

    return options

if __name__ == '__main__':
    options = handle_options()
    bsetup = BloodhoundSetup(options)
    bsetup.setup()
