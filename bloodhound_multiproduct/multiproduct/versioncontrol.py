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

"""Bloodhound version control support"""

import os.path

from trac.util.concurrency import threading
from trac.core import implements
import trac.versioncontrol.api
import trac.admin
import trac.web.api
import trac.resource
from multiproduct.util import ReplacementComponent

class DbRepositoryProvider(trac.versioncontrol.api.DbRepositoryProvider, ReplacementComponent):
    """Inplace replacement for trac.versioncontrol.api.DbRepositoryProvider. Filters
    repositories based on soft-links to products. Soft links are stored in 'product'
    repository attribute, separated by comma."""

    repository_attrs = trac.versioncontrol.api.DbRepositoryProvider.repository_attrs + tuple(['product'])

    implements(trac.versioncontrol.api.IRepositoryProvider,
               trac.admin.IAdminCommandProvider)

    # IRepositoryProvider methods
    def get_repositories(self):
        """Retrieve list of repositories specified in the repository
        table for current product environment
        """
        from multiproduct.env import ProductEnvironment
        if isinstance(self.env, ProductEnvironment):
            repos = {}
            for id, name, value in self.env.db_direct_query(
                "SELECT id, name, value FROM repository WHERE name IN (%s)"
                % ",".join("'%s'" % each for each in self.repository_attrs)):
                if value is not None:
                    repos.setdefault(id, {})[name] = value
            reponames = {}
            for id, info in repos.iteritems():
                if 'product' in info and \
                   not self.env.product.prefix in info['product'].split(','):
                    # skip repository if not soft linked from the current
                    # product environment
                    continue
                if 'product' in info:
                    del info['product']
                if 'name' in info and ('dir' in info or 'alias' in info):
                    info['id'] = id
                    reponames[info['name']] = info
            return reponames.iteritems()
        else:
            return super(DbRepositoryProvider, self).get_repositories()

trac.versioncontrol.api.DbRepositoryProvider = DbRepositoryProvider

class RepositoryManager(trac.versioncontrol.api.RepositoryManager, ReplacementComponent):

    implements(trac.web.api.IRequestFilter,
               trac.resource.IResourceManager,
               trac.versioncontrol.api.IRepositoryProvider)

    def __init__(self):
        super(RepositoryManager, self).__init__()

trac.versioncontrol.api.RepositoryManager = RepositoryManager
