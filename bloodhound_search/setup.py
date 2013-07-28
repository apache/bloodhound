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


import sys
from pkg_resources import parse_version
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

DESC = """Search plugin for Apache(TM) Bloodhound.

Add free text search and query functionality to Bloodhound sites.
"""

versions = [
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

DIST_NM = 'BloodhoundSearchPlugin'
PKG_INFO = {'bhsearch' : ('bhsearch',                     # Package dir
                            # Package data
                            ['../CHANGES', '../TODO', '../COPYRIGHT',
                              '../NOTICE', '../README', '../TESTING_README',
                              'htdocs/*.*', 'htdocs/css/*.css',
                              'htdocs/img/*.*', 'htdocs/js/*.js',
                              'templates/*', 'default-pages/*'],
                          ),
            'bhsearch.search_resources' : (
                'bhsearch/search_resources', # Package dir
                []
                ),
#            'search.widgets' : ('bhsearch/widgets',     # Package dir
#                            # Package data
#                            ['templates/*', 'htdocs/*.css'],
#                          ),
#            'search.layouts' : ('bhsearch/layouts',     # Package dir
#                            # Package data
#                            ['templates/*'],
#                          ),
            'bhsearch.tests' : ('bhsearch/tests',     # Package dir
                            # Package data
                            ['data/*.*'],
                          ),
            'bhsearch.tests.search_resources' : (
                'bhsearch/tests/search_resources',     # Package dir
                            # Package data
                            ['data/*.*'],
                          ),
            }

ENTRY_POINTS = {
    'trac.plugins': [
        'bhsearch.web_ui = bhsearch.web_ui',
        'bhsearch.api = bhsearch.api',
        'bhsearch.admin = bhsearch.admin',
        'bhsearch.search_resources.changeset_search =\
            bhsearch.search_resources.changeset_search',
        'bhsearch.search_resources.ticket_search =\
            bhsearch.search_resources.ticket_search',
        'bhsearch.search_resources.wiki_search = \
            bhsearch.search_resources.wiki_search',
        'bhsearch.search_resources.milestone_search = \
            bhsearch.search_resources.milestone_search',
        'bhsearch.query_parser = bhsearch.query_parser',
        'bhsearch.query_suggestion = bhsearch.query_suggestion',
        'bhsearch.security = bhsearch.security',
        'bhsearch.whoosh_backend = bhsearch.whoosh_backend',
    ],
    }
setup(
    name=DIST_NM,
    version=latest,
    description=DESC.split('\n', 1)[0],
    author = "Apache Bloodhound",
    license = "Apache License v2",
    url = "https://bloodhound.apache.org/",
    requires = ['trac'],
    install_requires = [
        'setuptools>=0.6b1',
        'Trac>=0.11',
        'whoosh==2.4.1',
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
    long_description= DESC,
    test_suite='bhsearch.tests.test_suite',
    tests_require=['unittest2' if parse_version(sys.version) < parse_version('2.7') else '']
    )

