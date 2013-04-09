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

"""
This module contains tests of search security using the actual permission
system backend.
"""
import contextlib
import unittest
from sqlite3 import OperationalError

from trac.perm import PermissionSystem, DefaultPermissionPolicy

from multiproduct.api import MultiProductSystem, ProductEnvironment

from bhsearch.tests.base import BaseBloodhoundSearchTest
from bhsearch.api import BloodhoundSearchApi
from bhsearch.whoosh_backend import WhooshBackend

# TODO: Convince trac to register modules without these imports
from trac.wiki import web_ui
from bhsearch import security



class MultiProductSecurityTestSuite(BaseBloodhoundSearchTest):
    def setUp(self):
        super(MultiProductSecurityTestSuite, self).setUp(
            enabled=['trac.*', 'trac.wiki.*', 'bhsearch.*', 'multiproduct.*'],
            create_req=True,
            enable_security=True,
            mock_multiproduct=False,
        )
        self.global_env = self.env
        self.product_envs = []

        self._setup_multiproduct()
        self._disable_trac_caches()
        self._create_whoosh_index()

        self.search_api = BloodhoundSearchApi(self.env)
        self._add_products('p1', 'p2')

    def test_applies_security(self):
        self.insert_ticket('ticket 1')

        with self.product('p1'):
            self.insert_wiki('page 1', 'content')
            self.insert_ticket('ticket 2')
        with self.product('p2'):
            self.insert_wiki('page 2', 'content 2')
            self.insert_ticket('ticket 3')

        results = self.search_api.query("type:wiki", context=self.context)
        self.assertEqual(results.hits, 0)

        self._add_permission('x', 'WIKI_VIEW')
        results = self.search_api.query("type:wiki", context=self.context)
        self.assertEqual(results.hits, 0)

        self._add_permission('x', 'WIKI_VIEW', 'p1')
        results = self.search_api.query("type:wiki", context=self.context)
        self.assertEqual(results.hits, 1)

        self._add_permission('x', 'WIKI_VIEW', 'p2')
        results = self.search_api.query("type:wiki", context=self.context)
        self.assertEqual(results.hits, 2)

        self._add_permission('x', 'TICKET_VIEW', 'p2')
        results = self.search_api.query("*", context=self.context)
        self.assertEqual(results.hits, 3)

        self._add_permission('x', 'TICKET_VIEW', 'p1')
        results = self.search_api.query("*", context=self.context)
        self.assertEqual(results.hits, 4)

        self._add_permission('x', 'TICKET_VIEW')
        results = self.search_api.query("*", context=self.context)
        self.assertEqual(results.hits, 5)

    def test_admin_has_access(self):
        with self.product('p1'):
            self.insert_wiki('page 1', 'content')
        self._add_permission('x', 'TRAC_ADMIN')
        results = self.search_api.query("*", context=self.context)
        self.assertEqual(results.hits, 1)

    def test_admin_granted_in_product_should_not_have_access(self):
        with self.product('p1'):
            self.insert_wiki('page 1', 'content')

        self._add_permission('x', 'TRAC_ADMIN', 'p1')
        results = self.search_api.query("*", context=self.context)
        self.assertEqual(results.hits, 1)

    def test_product_owner_has_access(self):
        self._add_products('p3', owner='x')
        with self.product('p3'):
            self.insert_ticket("ticket")

        results = self.search_api.query("*", context=self.context)
        self.assertEqual(results.hits, 1)

    def test_user_with_no_permissions(self):
        with self.product('p1'):
            self.insert_wiki('page 1', 'content')
        results = self.search_api.query("type:wiki", context=self.context)
        self.assertEqual(results.hits, 0)

    def test_adding_security_filters_retains_existing_filters(self):
        with self.product('p1'):
            self.insert_ticket("ticket 1")
            self.insert_ticket("ticket 2", status="closed")
        with self.product('p2'):
            self.insert_ticket("ticket 3", status="closed")

        self._add_permission('x', 'TICKET_VIEW', 'p1')
        self._add_permission('x', 'TICKET_VIEW', 'p2')

        results = self.search_api.query(
            "*",
            filter=["status:closed"],
            context=self.context
        )
        self.assertEqual(results.hits, 2)

    def _setup_multiproduct(self):
        try:
            MultiProductSystem(self.global_env)\
                .upgrade_environment(self.env.db_transaction)
        except OperationalError:
            # table remains but database version is deleted
            pass
        self.env.enable_multiproduct_schema()

    def _disable_trac_caches(self):
        DefaultPermissionPolicy.CACHE_EXPIRY = 0
        self._clear_permission_caches()

    def _create_whoosh_index(self):
        WhooshBackend(self.env).recreate_index()

    def _add_products(self, *products, **kwargs):
        owner = kwargs.pop('owner', '')
        with self.global_env.db_direct_transaction as db:
            for product in products:
                db("INSERT INTO bloodhound_product (prefix, owner) "
                   " VALUES ('%s', '%s')" % (product, owner))
                product = ProductEnvironment(self.global_env, product)
                self.product_envs.append(product)

    @contextlib.contextmanager
    def product(self, prefix=''):
        self.env = ProductEnvironment(self.global_env, prefix)
        yield
        self.env = self.global_env

    def _add_permission(self, username='', permission='', product=''):
        with self.global_env.db_direct_transaction as db:
            db("INSERT INTO permission (username, action, product)"
               "VALUES ('%s', '%s', '%s')" %
               (username, permission, product))
        self._clear_permission_caches()

    def _clear_permission_caches(self):
        for env in [self.global_env] + self.product_envs:
            del PermissionSystem(env).store._all_permissions


def suite():
    return unittest.makeSuite(MultiProductSecurityTestSuite, 'test')

if __name__ == '__main__':
    unittest.main()
