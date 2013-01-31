#!/usr/bin/env python
# -*- coding: UTF-8 -*-

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

r"""Administration commands for Bloodhound Search."""
from trac.core import Component, implements
from trac.admin import IAdminCommandProvider
from bhsearch.api import BloodhoundSearchApi

class BloodhoundSearchAdmin(Component):
    """Bloodhound Search administration component."""

    implements(IAdminCommandProvider)

    # IAdminCommandProvider methods
    def get_admin_commands(self):
        yield ('bhsearch rebuild', '',
            'Rebuild Bloodhound Search index',
            None, BloodhoundSearchApi(self.env).rebuild_index)
        yield ('bhsearch optimize', '',
            'Optimize Bloodhound search index',
            None, BloodhoundSearchApi(self.env).optimize)

