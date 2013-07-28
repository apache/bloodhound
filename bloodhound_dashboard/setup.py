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


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

DESC = """Project dashboard for Apache(TM) Bloodhound.

Add custom dashboards in multiple pages of Bloodhound sites.
"""

versions = [
    (0, 1, 0),
    (0, 2, 0),
    (0, 3, 0),
    (0, 4, 0),
    (0, 5, 0),
    (0, 6, 0),
    (0, 7, 0),
    ]
    
latest = '.'.join(str(x) for x in versions[-1])

status = {
            'planning' :  "Development Status :: 1 - Planning",
            'pre-alpha' : "Development Status :: 2 - Pre-Alpha",
            'alpha' :     "Development Status :: 3 - Alpha",
            'beta' :      "Development Status :: 4 - Beta",
            'stable' :    "Development Status :: 5 - Production/Stable",
            'mature' :    "Development Status :: 6 - Mature",
            'inactive' :  "Development Status :: 7 - Inactive"
         }
dev_status = status["alpha"]

cats = [
      dev_status,
      "Environment :: Plugins", 
      "Environment :: Web Environment", 
      "Framework :: Trac", 
      "Intended Audience :: Developers", 
      "Intended Audience :: Information Technology", 
      "Intended Audience :: Other Audience", 
      "Intended Audience :: System Administrators", 
      "License :: Unknown", 
      "Operating System :: OS Independent", 
      "Programming Language :: Python", 
      "Programming Language :: Python :: 2.5", 
      "Programming Language :: Python :: 2.6",
      "Programming Language :: Python :: 2.7",
      "Topic :: Internet :: WWW/HTTP :: Dynamic Content :: CGI Tools/Libraries", 
      "Topic :: Internet :: WWW/HTTP :: HTTP Servers", 
      "Topic :: Internet :: WWW/HTTP :: WSGI", 
      "Topic :: Software Development :: Bug Tracking", 
      "Topic :: Software Development :: Libraries :: Application Frameworks", 
      "Topic :: Software Development :: Libraries :: Python Modules", 
      "Topic :: Software Development :: User Interfaces",
      "Topic :: Software Development :: Widget Sets"
    ]

# Add the change log to the package description.
chglog = None
try:
    from os.path import dirname, join
    chglog = open(join(dirname(__file__), "CHANGES"))
    DESC+= ('\n\n' + chglog.read())
finally:
    if chglog:
        chglog.close()

DIST_NM = 'BloodhoundDashboardPlugin'
PKG_INFO = {'bhdashboard' : ('bhdashboard',                     # Package dir
                            # Package data
                            ['../CHANGES', '../TODO', '../COPYRIGHT', 
                              '../NOTICE', '../README', '../TESTING_README',
                              'htdocs/*.*', 'htdocs/css/*.css',
                              'htdocs/img/*.*', 'htdocs/js/*.js',
                              'templates/*', 'default-pages/*'],
                          ), 
            'bhdashboard.widgets' : ('bhdashboard/widgets',     # Package dir
                            # Package data
                            ['templates/*', 'htdocs/*.css'],
                          ), 
            'bhdashboard.layouts' : ('bhdashboard/layouts',     # Package dir
                            # Package data
                            ['templates/*'],
                          ), 
            'bhdashboard.tests' : ('bhdashboard/tests',     # Package dir
                            # Package data
                            ['data/**'],
                          ), 
            }

ENTRY_POINTS = r"""
               [trac.plugins]
               bhdashboard.admin = bhdashboard.admin
               bhdashboard.api = bhdashboard.api
               bhdashboard.macros = bhdashboard.macros
               bhdashboard.layouts.bootstrap = bhdashboard.layouts.bootstrap
               bhdashboard.widgets.containers = bhdashboard.widgets.containers
               bhdashboard.widgets.product = bhdashboard.widgets.product
               bhdashboard.widgets.query = bhdashboard.widgets.query
               bhdashboard.widgets.report = bhdashboard.widgets.report
               bhdashboard.widgets.ticket = bhdashboard.widgets.ticket
               bhdashboard.widgets.timeline = bhdashboard.widgets.timeline
               bhdashboard.wiki = bhdashboard.wiki
               """

setup(
    name=DIST_NM,
    version=latest,
    description=DESC.split('\n', 1)[0],
    author = "Apache Bloodhound",
    license = "Apache License v2",
    url = "https://bloodhound.apache.org/",
    requires = ['trac'],
    tests_require = ['dutest>=0.2.4', 'TracXMLRPC'],
    install_requires = [
        'setuptools>=0.6b1',
        'Trac>=0.11',
    ],
    package_dir = dict([p, i[0]] for p, i in PKG_INFO.iteritems()),
    packages = PKG_INFO.keys(),
    package_data = dict([p, i[1]] for p, i in PKG_INFO.iteritems()),
    include_package_data=True,
    provides = ['%s (%s)' % (p, latest) for p in PKG_INFO.keys()],
    obsoletes = ['%s (>=%s.0.0, <%s)' % (p, versions[-1][0], latest) \
                  for p in PKG_INFO.keys()],
    entry_points = ENTRY_POINTS,
    classifiers = cats,
    long_description= DESC
    )

