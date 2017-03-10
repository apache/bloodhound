#!/usr/bin/env python
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

from setuptools import setup

DESC = """Installer for Apache Bloodhound

Adds the bloodhound_setup cli command.
"""

versions = [
    (0, 8, 0),
    (0, 9, 0),
]

latest = '.'.join(str(x) for x in versions[-1])

setup(
    name="bloodhound_installer",
    version=latest,
    description=DESC.split('\n', 1)[0],
    author="Apache Bloodhound",
    license="Apache License v2",
    url="https://bloodhound.apache.org/",
    requires=['trac', 'BloodhoundMultiProduct'],
    packages=['bhsetup'],
    entry_points="""
        [console_scripts]
        bloodhound_setup = bhsetup.bloodhound_setup:run
        """,
    long_description=DESC,
)
