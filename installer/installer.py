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

"""Installer for Bloodhound - depends on the supplied requirements.txt file
to determine the installation packages"""

import os
from optparse import OptionParser
import subprocess
import platform
import sys
from getpass import getpass

import virtualenv
from createdigest import htdigest_create

if not hasattr(virtualenv, 'logger'):
    virtualenv.logger = virtualenv.Logger([(virtualenv.Logger.LEVELS[-1], 
                                          sys.stdout)])

DEFAULT_DB_USER = 'bloodhound'
DEFAULT_DB_NAME = 'bloodhound'
DEFAULT_ADMIN_USER = 'admin'

BASE_CONFIG = """
[components]
bhtheme.* = enabled
bhdashboard.* = enabled
multiproduct.* = enabled
themeengine.* = enabled
trac.ticket.web_ui.ticketmodule = disabled

[header_logo]
src = 

[theme]
theme = bloodhound
"""

ACCOUNTMGRSTR = """
[account-manager]
account_changes_notify_addresses = 
authentication_url = 
db_htdigest_realm = 
force_passwd_change = true
hash_method = HtDigestHashMethod
htdigest_file = %(htdigest)s
htdigest_realm = %(realm)s
htpasswd_file = 
htpasswd_hash_type = crypt
password_file = %(htdigest)s
password_store = HtDigestStore
persistent_sessions = False
refresh_passwd = False
user_lock_max_time = 0
verify_email = True

[components]
acct_mgr.admin.*= enabled
acct_mgr.api.accountmanager = enabled
acct_mgr.guard.accountguard = enabled
acct_mgr.htfile.htdigeststore = enabled
acct_mgr.web_ui.accountmodule = enabled
acct_mgr.web_ui.loginmodule = enabled
trac.web.auth.loginmodule = disabled
"""

def install_virtualenv(venvpath, syspackages):
    """Install virtualenv - should be done before any pip installs, and
    runs a command like: virtualenv bloodhound --no-site-packages
    """
    create_env_cmd = ['virtualenv', venvpath]
    if not syspackages:
        create_env_cmd.append('--no-site-packages')
    print 'Running: ' + ' '.join(create_env_cmd)
    try:
        code = subprocess.call(create_env_cmd)
    except OSError:
        print "Could not create the virtualenv - is virtualenv installed?"
        sys.exit(-1)
    if code != 0:
        print "Creation of virtual environment failed. Exit code=", code
        sys.exit(code)

def trac_config_create(adminuser, adminpass, realm, digestfile, trac_ini):
    """Create the config and optionally a htdigest file"""
    config_str = ''
    config_str += BASE_CONFIG
    
    htdigest_create(digestfile, adminuser, realm, adminpass)
    # adding appropriate configuration to use the digestfile with the
    # account manager plugin
    config_str += ACCOUNTMGRSTR % {'htdigest':digestfile,
                                   'realm':realm}
    with open(trac_ini, 'a') as inifile:
        inifile.write(config_str)
    return adminpass

def do_install(options):
    """Perform the installation"""
    data = {'dbuser':options.dbuser, 'dbpass':options.dbpass,
            'host':options.dbhost, 'dbname':options.dbname}
    dbtype = options.dbtype.lower()
    
    if (not options.dbuser or not options.dbpass) and dbtype != 'sqlite':
        dbtype = 'sqlite'
    if dbtype in ['postgres', 'postgresql']:
        dbstr = 'postgres://%(dbuser)s:%(dbpass)s@%(host)s/%(dbname)s' % data
    else:
        dbstr = 'sqlite:db/bloodhound.db'
    
    bindir = os.path.join(options.venvpath,'bin')
    admin = os.path.join(bindir, 'trac-admin')
    
    virtualenv.create_environment(options.venvpath, 
                                  site_packages=options.syspackages)
    
    def run_pip(venvpath, requirements):
        """Run pip install"""
        if platform.system() in ('Windows', 'Microsoft'):
            pip = os.path.join(venvpath, 'scripts', 'pip')
        else:
            pip = os.path.join(venvpath, 'bin', 'pip')
        prefix = os.path.abspath(venvpath)
        code = subprocess.call([pip, 'install',
                                '--requirement=%s' % requirements,
                                '--install-option=--prefix=%s' % prefix])
                      #'--environment=%s' % venvpath,
        if code:
            raise Exception
        return code
    
    if dbtype in ['postgres', 'postgresql']:
        run_pip(options.venvpath, 'pgrequirements.txt')
    run_pip(options.venvpath, options.requirements)
    
    environments_path = os.path.join(options.venvpath, 'environments')
    if not os.path.exists(environments_path):
        os.makedirs(environments_path)
    
    new_env = os.path.join(environments_path, options.project)
    
    if platform.system() in ('Windows', 'Microsoft'):
        data['activate'] = os.path.join(bindir,'activate.bat')
    else:
        data['activate'] = 'source ' + os.path.join(bindir, 'activate')
    project_dir = os.path.join(environments_path,
                               options.project)
    data['tracd'] = 'tracd --port=8000 ' + project_dir
    digestfile = os.path.abspath(
            os.path.join(environments_path,options.digestfile)
            )
    base_ini = os.path.abspath(
            os.path.join(environments_path, 'base.ini')
            )
    trac_config_create(options.adminuser, options.adminpass, options.realm,
            digestfile, base_ini)

    def trac_admin_run_cmd(cmd):
        """Runs a command (assumes that it is trac-admin)"""
        print 'Running: ' + ' '.join(cmd)
        try:
            code = subprocess.call(cmd)
        except OSError:
            print "Error: trac-admin command was not installed in previous step"
            sys.exit(-3)
        if code != 0:
            print "Error while running trac-admin command. Exit code=", code
            sys.exit(code)

    
    trac_admin_run_cmd([admin, new_env, 'initenv', options.project, dbstr,
                       '--inherit=%s' % base_ini])
    trac_admin_run_cmd([admin, new_env, 'upgrade'])
    trac_admin_run_cmd([admin, new_env, 'wiki', 'upgrade'])
    trac_admin_run_cmd([admin, new_env, 'permission', 'add', options.adminuser,
                        'TRAC_ADMIN'])
    
    print """To run you must first activate the virtual environment: 
  %(activate)s
then:
  %(tracd)s""" % data
    

def main():
    """Parse arguments and call the installer function"""
    parser = OptionParser()
    parser.add_option('-e', '--environment', dest='venvpath',
                      help='Use virtual environment name',
                      default='bloodhound')
    parser.add_option('--project', dest='project',
                      help='Set the top project name', default='main')
    parser.add_option('-r', '--requirements', dest='requirements',
                      help='Use requirements file',
                      default='requirements.txt')
    parser.add_option('-d', '--database-type', dest='dbtype',
                      help="Specify as one of 'postgres' or 'sqlite'",
                      default='')
    parser.add_option('--database-name', dest='dbname',
                      help='Specify the database name (option for postgres)')
    parser.add_option('-u', '--user', dest='dbuser',
                      help='Specify the db user (required for postgres)',
                      default='')
    parser.add_option('-p', '--password', dest='dbpass',
                      help='Specify the db password (option for postgres)')
    parser.add_option('--database-host', dest='dbhost',
                      help='Specify the database host (optional for postgres)',
                      default='localhost')
    parser.add_option('--no-site-packages', dest='syspackages',
                      action='store_false', default=True,
                      help="Don't use system installed packages in virtualenv")
    parser.add_option('--admin-password', dest='adminpass',
                      help='create an admin user in an htdigest file')
    parser.add_option('--digest-realm', dest='realm', default='bloodhound',
                      help='authentication realm for htdigest file')
    parser.add_option('--admin-user', dest='adminuser', default='',
                      help='admin user name for htdigest file')
    parser.add_option('--digest-file', dest='digestfile',
                      default='bloodhound.htdigest',
                      help='filename for the htdigest file')
    
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
        answer = ask_question("""
This installer is able to install Apache Bloodhound with either SQLite or
PostgreSQL databases. SQLite is an easier option for installing Bloodhound as
SQLite is usually built into Python and also requires no special permissions to
run. However, PostgreSQL is generally expected to be more robust for production
use.
Do you want to install to a PostgreSQL database [Y/n]: """)
        options.dbtype = 'postgres' if answer.lower() not in ['n','no'] else 'sqlite'
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
    
    do_install(options)

if __name__ == '__main__':
    main()

