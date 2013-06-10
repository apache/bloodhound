==========================================
 General Installation of Apache Bloodhound
==========================================

With the basic scripts in this directory you will eventually be able to install
the Apache Bloodhound source with limited fuss.

The following describes how to install using the bloodhound_setup.py script
with either SQLite or PostgreSQL databases.

For simplicity, this document usually describes installation from the point of
view of using Ubuntu 11.10 and so commands will probably have to be adjusted
to take your operating system version into account.

General Prerequisites
=====================

The provided script requires at least:

 * Python (2.6 >= version < 3.0)
 * setuptools
 * pip
 * virtualenv

Most distributions of linux should have these in their repositories (pip and
virtualenv are likely to be python-pip and python-virtualenv respectively).
If these are not readily available, the instructions for downloading and 
installing for your system should be at:

 * Python: http://www.python.org/
 * setuptools: http://pypi.python.org/pypi/setuptools#id1
 * pip: http://www.pip-installer.org/en/latest/installing.html

Once you have pip you should be able to::
 pip install virtualenv

Database Prerequisites
======================

Although Apache Bloodhound supports a number of databases, this installer
currently only sets up either SQLite or PostgreSQL databases.

Installing Apache Bloodhound with SQLite should be considerably easier than
PostgreSQL as Python comes with SQLite integrated into it. In addition, no
special access rights are required to create an SQLite database as it is stored
in a local file.

However, SQLite may not be appropriate for larger production installations and
so using PostgreSQL is generally encouraged. On the other hand, for less
intensive use or evaluation, SQLite should be a good choice. If you think that
SQLite is for you, skip to the next section now.

Using PostgreSQL is complicated by having to create users and a database on
the server and the appropriate permissions to access it. It also adds the
following dependencies:

 * PostgreSQL
 * psycopg2

Again, for linux distributions, these are probably available from the relevant
distribution repositories. Otherwise you should be able to download and find
instructions for installing from:

 * PostgreSQL: http://www.postgresql.org/
 * psycopg2: http://initd.org/psycopg/

Alternatively, it might be possible to install psycopg2 with a pip install
command but this may require additional dependencies to compile the package.
This is also why it is generally considered a prerequisite.

With these in place, you will also need to add a user and database and make sure
that the created user is able to access the database. For example::

  $ sudo su - postgres
  $ createuser -U postgres -S -D -R -E -P bloodhound
  $ createdb -U postgres -O bloodhound -E UTF-8 bloodhound
  $ logout

and (on Ubuntu 11.10)::

  $ sudo vi /etc/postgresql/9.1/main/pg_hba.conf

In that file you should change::
  local   all             all                                     peer
to::
  local   all             all                                     md5

After saving and restarting the database::
  $ sudo /etc/init.d/postgresql restart

Getting Apache Bloodhound
=========================

Bloodhound can currently be checkout out from the apache subversion servers::

  $ svn co https://svn.apache.org/repos/asf/bloodhound/trunk bloodhound

Installation and Initial Configuration
======================================

Environment setup is achieved with the following commands on linux::

  $ cd bloodhound/installer
  $ virtualenv --system-site-packages bloodhound
  $ source ./bloodhound/bin/activate

or on windows::

  $ cd bloodhound\installer
  $ virtualenv --system-site-packages bloodhound
  $ bloodhound\bin\activate.bat

From now on, all shell commands should be run within the activated virtualenv
so run::

  $ source ./bloodhound/bin/activate

or::

  $ bloodhound\bin\activate.bat

as appropriate if you need to continue running these instructions in a fresh 
shell.

Next you should install the required python packages with::

  $ pip install -r requirements-dev.txt

Bloodhound provides a script to create the database, set up an initial admin
user and provide an initial configuration. If no options are provided, the
installer will ask you some of the more important questions to help set up 
Apache Bloodhound. As such you can just run::

  $ python bloodhound_setup.py

and answer the questions, providing details depending on the choices you made
about the database.

Specifically, if you choose SQLite, you will only be asked to provide an admin
user name and a password to use. For the PostgreSQL choice, you are also asked
for the database name, database user and the associated password.

It is also possible to specify all these details on the command line and set
additional options like the host for the postgres database and the location of
the installation. For more information on these options, try running::

  $ python bloodhound_setup.py --help

Testing the Server
==================

The successful running of bloodhound_setup.py should provide you with an
appropriate command to run and the url to check for success. If you have not
specified any advanced options for the bloodhound_setup.py script, you should
be able to run bloodhound using::

  $ tracd ./bloodhound/environments/main --port=8000

At this point you should be able to access Apache Bloodhound on
  http://localhost:8000/main/

where you can login with the admin user and password details you supplied.

Web Server
==========

If you have managed to prove that you can run the system with the standalone
tracd, you should now also be able to run through a web server. Here we provide
details about how to use the Apache webserver. It is currently recommended to
use Apache with mod_wsgi to serve Bloodhound. The following instructions
require Apache HTTP Server to be installed along with the wsgi and auth_digest
modules.

It is possible to get the trac-admin command to reduce some of the work of
creating the wsgi file::

  $ source ./bloodhound/bin/activate
  $ trac-admin ./bloodhound/environments/main deploy ./bloodhound/site

You should also make sure that the appropriate modules are enabled for wsgi
and htdigest authentication. On Ubuntu this would be::

  $ sudo a2enmod wsgi
  $ sudo a2enmod auth_digest

You will then need to create a site configuration for Apache. In Ubuntu this can
be done like this::

  $ sudo vi /etc/apache2/sites-available/bloodhound

Add to this something like::

  <VirtualHost *:8080>
    WSGIDaemonProcess bloodhound_tracker user=bloodhound python-path=/path/to/bloodhound/lib/python2.7/site-packages
    WSGIScriptAlias /bloodhound /path/to/bloodhound/site/cgi-bin/trac.wsgi
    <Directory /path/to/bloodhound/site/cgi-bin>
      WSGIProcessGroup bloodhound_tracker
      WSGIApplicationGroup %{GLOBAL}
      Order deny,allow
      Allow from all
    </Directory>
    <LocationMatch "/bloodhound/[^/]+/login">
      AuthType Digest
      AuthName "Bloodhound"
      AuthDigestDomain /bloodhound
      AuthUserFile /path/to/bloodhound/environments/main/bloodhound.htdigest
      Require valid-user
    </LocationMatch>
  </VirtualHost>

The user referred to in the WSGIDaemonProcess should be the user that you wish
bloodhound to be run as and so that user must have the appropriate set of
permissions to access the Bloodhound installation. Running with any special
system level privileges should not be required and is not recommended.

Then enable the new site, check the apache configuration and restart apache::

  $ sudo a2ensite bloodhound
  $ sudo apachectl configtest
  $ sudo apachectl graceful

If that all worked, you will now be able to see Apache Bloodhound running on:
  http://localhost:8080/bloodhound/

Notes on Authentication
=======================

The installation procedure assumes that you will want to create an admin user
to access the site with. The details can be specified by the --admin-user and
--admin-password options. If they are not provided, the script will ask for the
details instead. The authentication mechanism is created from these details by
creating an htdigest file, setting up htdigest authentication with the account
manager and giving the initial user full admin access in the web frontend.

It is also possible to set the digest realm by using the --digest-realm option.

Once you are running the web application, it is possible to modify the
authentication mechanism further through the admin pages.

Overview of Manual Installation Instruction Assuming Ubuntu 11.10
=================================================================

The following table describes steps to install bloodhound with (at least) the
following assumptions:

 * Ubuntu 11.10
 * Python already installed
 * Required database installed (not the python bindings)
 * Database user and database created (not for SQLite) and
   * the database will be on localhost (default port)
   * db user is user; db user's password is pass; database name is dbname

A current specific difference from using bloodhound_setup.py to provide the
initial configuration is that the bloodhound.htdigest and base.ini are in the
bloodhound/environments directory instead of bloodhound/environments/main.

+---------------------+-------------------------------------------------+----------------------------------------+
| Step Description    | Common Steps                                    | Optional (recommended) Steps           |
+=====================+=================================================+========================================+
| install pip         | sudo apt-get install python-pip                 |                                        |
+---------------------+-------------------------------------------------+----------------------------------------+
| install virtualenv  |                                                 | sudo apt-get install python-virtualenv |
+---------------------+-------------------------------------------------+----------------------------------------+
| create and activate |                                                 | virtualenv bloodhound                  |
|  an environment     |                                                 | source bloodhound/bin/activate         |
+---------------------+-------------------------------------------------+----------------------------------------+
|                     | commands from now on should be run in the active env - the next step will require        |
|                     |  running with sudo if you did not create and activate a virtualenv                       |
+---------------------+-------------------------------------------------+----------------------------------------+
| install reqs        | pip install -r requirements-dev.txt             |                                        |
+---------------------+-------------------------------------------------+----------------------------------------+
| create environments | mkdir -p bloodhound/environments/               |                                        |
|  directory          | cd bloodhound/environments/                     |                                        |
+---------------------+-------------------------------------------------+----------------------------------------+
| create htdigest     | python ../../createdigest.py --user=admin \     |                                        |
|                     |   --password=adminpasswd --realm=bloodhound \   |                                        |
|                     |   -f bloodhound.htdigest                        |                                        |
+---------------------+-------------------------------------------------+----------------------------------------+
| add a base config   | nano base.ini                                   |                                        |
|  file (see below)   |                                                 |                                        |
+---------------------+-------------------------------------------------+----------------------------------------+

In base.ini save the following (replacing each /path/to with the real path)::

 [account-manager]
 account_changes_notify_addresses =
 authentication_url =
 db_htdigest_realm =
 force_passwd_change = true
 hash_method = HtDigestHashMethod
 htdigest_file = /path/to/bloodhound/environments/bloodhound.htdigest
 htdigest_realm = bloodhound
 htpasswd_file =
 htpasswd_hash_type = crypt
 password_file = /path/to/bloodhound/environments/bloodhound.htdigest
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
 bhtheme.* = enabled
 bhdashboard.* = enabled
 multiproduct.* = enabled
 themeengine.* = enabled
 trac.ticket.report.reportmodule = disabled
 trac.ticket.web_ui.ticketmodule = disabled
 trac.web.auth.loginmodule = disabled

 [header_logo]
 src =

 [mainnav]
 browser.label = Source
 roadmap = disabled
 timeline = disabled
 tickets.label = Tickets

 [theme]
 theme = bloodhound

 [trac]
 mainnav = dashboard,wiki,browser,tickets,newticket,timeline,roadmap,search,admin

The double specification of htdigest_file and password_file is because of
differences between versions of the account manager plugin.

Continue with the following table that shows the completion of the installation
for a few databases types.

+----------------------+-------------------------------------------------+--------------------------------------------+-------------------+
| Step Description     | Common Steps                                    | PostgreSQL Only                            | SQLite Only       |
+======================+=================================================+============================================+===================+
| install python       |                                                 | sudo apt-get install python-psycopg2       |                   |
|  database bindings   |                                                 |                                            |                   |
+----------------------+-------------------------------------------------+--------------------------------------------+-------------------+
| set $DBSTRING adding | export DBSTRING=[db specific string ->]         | postgres://user:pass@localhost:5432/dbname | sqlite:db/trac.db |
|  db specific string  |                                                 |                                            |                   |
+----------------------+-------------------------------------------------+--------------------------------------------+-------------------+
| initialise           | trac-admin main initenv ProjectName $DBSTRING \ |                                            |                   |
|                      |   --inherit=path/to/base.ini                    |                                            |                   |
+----------------------+-------------------------------------------------+--------------------------------------------+-------------------+
| upgrade wiki         | trac-admin main wiki upgrade                    |                                            |                   |
| set permissions      | trac-admin main permission add admin TRAC_ADMIN |                                            |                   |
+----------------------+-------------------------------------------------+--------------------------------------------+-------------------+

Now it should be possible to start bloodhound with::

  $ tracd --port=8000 main

and login from http://localhost:8000/main/login

Also note that if you are starting from a new shell session, if you are using
virtualenv you should::

  $ source path/to/bloodhound/bin/activate

then::

  $ tracd --port=8000 path/to/bloodhound/environments/main

