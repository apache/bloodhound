
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

"""setup for multi product plugin"""
import sys, codecs
from pkg_resources import parse_version
from setuptools import setup


# Force UTF-8 for stdout/err if --utf8 option is specified.
# For some reason python doesn't obey LANG/LC_CTYPE settings
# if output is not a terminal (e.g. pipes don't work).
if __name__ == '__main__':
    for ac,av in enumerate(sys.argv):
        if av == '--utf8':
            sys.stdout = codecs.getwriter('utf8')(sys.stdout)
            sys.stderr = codecs.getwriter('utf8')(sys.stderr)
            del sys.argv[ac]
            break

setup(
    name = 'BloodhoundMultiProduct',
    version = '0.7.0',
    description = "Multiproduct support for Apache(TM) Bloodhound.",
    author = "Apache Bloodhound",
    license = "Apache License v2",
    url = "https://bloodhound.apache.org/",
    packages = ['multiproduct', 'multiproduct.ticket', 'tests',],
    package_data = {'multiproduct' : ['templates/*.html',]},
    entry_points = {'trac.plugins': [
            'multiproduct.model = multiproduct.model',
            'multiproduct.perm = multiproduct.perm',
            'multiproduct.product_admin = multiproduct.product_admin',
            'multiproduct.ticket.batch = multiproduct.ticket.batch',
            'multiproduct.ticket.query = multiproduct.ticket.query',
            'multiproduct.ticket.web_ui = multiproduct.ticket.web_ui',
            'multiproduct.web_ui = multiproduct.web_ui',
        ],},
    test_suite='tests.test_suite',
    tests_require=['unittest2' if parse_version(sys.version) < parse_version('2.7') else '']
)

