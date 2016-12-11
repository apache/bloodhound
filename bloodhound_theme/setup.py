#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

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

from setuptools import setup

extra = {}
try:
    from trac.util.dist import get_l10n_js_cmdclass

    cmdclass = get_l10n_js_cmdclass()
    if cmdclass:
        extra['cmdclass'] = cmdclass
        extractors = [
            ('**.py', 'trac.dist:extract_python', None),
            ('**/templates/**.html', 'genshi', None),
            ('**/templates/**.txt', 'genshi', {
                'template_class': 'genshi.template:TextTemplate'
            }),
        ]
        extra['message_extractors'] = {
            'bhtheme': extractors,
        }
except ImportError:
    pass

setup(
    name='BloodhoundTheme',
    version='0.9.0',
    description="Theme for Apache(TM) Bloodhound.",
    author="Apache Bloodhound",
    license="Apache License v2",
    url="https://bloodhound.apache.org/",
    keywords="trac plugin theme bloodhound",
    packages=['bhtheme'],
    package_data={'bhtheme': ['htdocs/*.*', 'htdocs/img/*.*',
                              'htdocs/js/*.js', 'htdocs/css/*.css',
                              'templates/*.*', 'locale/*/LC_MESSAGES/*.mo']},
    classifiers=[
        'Framework :: Trac',
    ],
    install_requires=['BloodhoundDashboardPlugin', 'TracThemeEngine'],
    test_suite='bhtheme.tests.suite',
    tests_require=['unittest2'] if sys.version_info < (2, 7) else [],
    entry_points={
        'trac.plugins': ['bhtheme.theme = bhtheme.theme']
    },
    **extra
)
