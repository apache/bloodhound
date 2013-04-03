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
from trac.versioncontrol import RepositoryManager
import trac.admin
import trac.web.api
import trac.resource
from multiproduct.util import ReplacementComponent
from multiproduct.env import ProductEnvironment

class DbRepositoryProvider(ReplacementComponent, trac.versioncontrol.api.DbRepositoryProvider):
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
        if isinstance(self.env, ProductEnvironment):
            repos = {}
            for id, name, value in self.env.db_direct_query(
                "SELECT id, name, value FROM repository WHERE name IN (%s)"
                % ",".join("'%s'" % each for each in self.repository_attrs)):
                if value is not None:
                    repos.setdefault(id, {})[name] = value
            reponames = {}
            for id, info in repos.iteritems():
                if not 'product' in info or \
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

    def _get_repository_links(self, repoid):
        with self.env.db_direct_query as db:
            rows = db("""SELECT value FROM repository WHERE id=%s
                         AND name='product'""" % (repoid,))
            if rows:
                return rows[0][0].split(',')
        return None

    def link_product(self, reponame):
        if not isinstance(self.env, ProductEnvironment):
            return
        rm = RepositoryManager(self.env.parent)
        repoid = rm.get_repository_id(reponame)
        links = self._get_repository_links(repoid)
        with self.env.db_direct_transaction as db:
            if links:
                links.append(self.env.product.prefix)
                db("""UPDATE repository SET value=%s WHERE id=%s
                      AND name='product'""", (','.join(links), repoid))
            else:
                db("""INSERT INTO repository (id, name, value)
                        VALUES(%s, 'product', '%s')""" %
                        (repoid, self.env.product.prefix))

    def unlink_product(self, reponame):
        if not isinstance(self.env, ProductEnvironment):
            return
        rm = RepositoryManager(self.env.parent)
        repoid = rm.get_repository_id(reponame)
        links = self._get_repository_links(repoid)
        links.remove(self.env.product.prefix)
        with self.env.db_direct_transaction as db:
            if len(links) > 0:
                db("""UPDATE repository SET value=%s WHERE id=%s
                      AND name='product'""", (','.join(links), repoid))
            else:
                db("""DELETE FROM repository WHERE id=%s AND name='product'
                        AND value='%s'""" % (repoid, self.env.product.prefix))

trac.versioncontrol.api.DbRepositoryProvider = DbRepositoryProvider
trac.versioncontrol.DbRepositoryProvider = DbRepositoryProvider

