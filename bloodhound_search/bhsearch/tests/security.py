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
import os
from sqlite3 import OperationalError

from trac.perm import (DefaultPermissionPolicy, PermissionCache,
                       PermissionSystem)

from bhsearch.api import BloodhoundSearchApi
from bhsearch.tests import unittest
from bhsearch.tests.base import BaseBloodhoundSearchTest
from bhsearch.whoosh_backend import WhooshBackend
from multiproduct.api import MultiProductSystem, ProductEnvironment

# TODO: Convince trac to register modules without these imports
from trac.wiki import web_ui
from bhsearch import security


class SecurityTest(BaseBloodhoundSearchTest):
    def setUp(self, enabled=[]):
        super(SecurityTest, self).setUp(
            enabled=enabled + ['trac.*', 'trac.wiki.*', 'bhsearch.*', 'multiproduct.*'],
            create_req=True,
            enable_security=True,
        )
        self.env.parent = None
        self.product_envs = []
        self.req.perm = PermissionCache(self.env, 'x')

        self._setup_multiproduct()
        self._disable_trac_caches()
        self._create_whoosh_index()

        self.search_api = BloodhoundSearchApi(self.env)
        self._add_products('p1', 'p2')

    def _setup_multiproduct(self):
        try:
            MultiProductSystem(self.env)\
                .upgrade_environment(self.env.db_transaction)
        except OperationalError:
            # table remains but content is deleted
            self._add_products('@')
        self.env.enable_multiproduct_schema()

    def _disable_trac_caches(self):
        DefaultPermissionPolicy.CACHE_EXPIRY = 0
        self._clear_permission_caches()

    def _create_whoosh_index(self):
        WhooshBackend(self.env).recreate_index()

    def _add_products(self, *products, **kwargs):
        owner = kwargs.pop('owner', '')
        with self.env.db_direct_transaction as db:
            for product in products:
                db("INSERT INTO bloodhound_product (prefix, owner) "
                   " VALUES ('%s', '%s')" % (product, owner))
                product = ProductEnvironment(self.env, product)
                self.product_envs.append(product)

    @contextlib.contextmanager
    def product(self, prefix=''):
        global_env = self.env
        self.env = ProductEnvironment(global_env, prefix)
        yield
        self.env = global_env

    def _add_permission(self, username='', permission='', product=''):
        with self.env.db_direct_transaction as db:
            db("INSERT INTO permission (username, action, product)"
               "VALUES ('%s', '%s', '%s')" %
               (username, permission, product))
        self._clear_permission_caches()

    def _clear_permission_caches(self):
        for env in [self.env] + self.product_envs:
            del PermissionSystem(env).store._all_permissions


class MultiProductSecurityTestSuite(SecurityTest):
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

    def test_product_dropdown_with_no_permission(self):
        self._add_permission('x', 'SEARCH_VIEW')
        data = self.process_request()

        product_list = data['search_product_list']
        self.assertEqual(len(product_list), 2)

    def test_product_dropdown_with_trac_admin_permission(self):
        self._add_permission('x', 'SEARCH_VIEW')
        self._add_permission('x', 'TRAC_ADMIN')
        data = self.process_request()

        product_list = data['search_product_list']
        self.assertEqual(len(product_list), 5)

    def test_product_dropdown_with_product_view_permissions(self):
        self._add_permission('x', 'SEARCH_VIEW')
        self._add_permission('x', 'PRODUCT_VIEW', '@')
        data = self.process_request()

        product_list = data['search_product_list']
        self.assertEqual(len(product_list), 3)

    def test_check_permission_is_called_with_advanced_security(self):
        self.env.config.set('bhsearch', 'advanced_security', "True")
        self.insert_ticket('ticket 1')
        with self.product('p1'):
            self.insert_wiki('page 1', 'content')
            self.insert_ticket('ticket 2')
        with self.product('p2'):
            self.insert_wiki('page 2', 'content 2')
            self.insert_ticket('ticket 3')
        self._add_permission('x', 'TRAC_ADMIN')

        calls = []

        def check_permission(self, doc, context):
            # pylint: disable=unused-argument
            calls.append((doc, context))
            return True

        security.SecurityPreprocessor.check_permission = check_permission

        results = self.search_api.query(
            "*",
            context=self.context
        )

        self.assertEqual(results.hits, 5)
        self.assertEqual(len(calls), 5)

    def test_advanced_security_overrides_normal_permissions(self):
        self.env.config.set('bhsearch', 'advanced_security', "True")
        self.insert_ticket('ticket 1')
        with self.product('p1'):
            self.insert_ticket('ticket 2')
        self._add_permission('x', 'TRAC_ADMIN')

        security.SecurityPreprocessor.check_permission = \
            lambda x, doc, z: doc['product'] == 'p1'

        results = self.search_api.query(
            "*",
            context=self.context
        )

        self.assertEqual(results.hits, 1)


class AuthzSecurityTestCase(SecurityTest):
    def setUp(self, enabled=()):
        SecurityTest.setUp(self, enabled=['tracopt.perm.authz_policy.*'])
        self.authz_config = os.path.join(self.env.path, 'authz.conf')
        self.env.config['authz_policy'].set('authz_file', self.authz_config)
        self.env.config['trac'].set('permission_policies',
                                    'AuthzPolicy,DefaultPermissionPolicy,'
                                    'LegacyAttachmentPolicy')

        # Create some dummy objects
        self.insert_ticket('ticket 1')
        self.insert_wiki('page 1', 'content')
        with self.product('p1'):
            self.insert_ticket('ticket 2')
            self.insert_wiki('page 1', 'content')

    def test_authz_permissions(self):
        self._add_permission('x', 'WIKI_VIEW')
        self.write_authz_config('\n'.join([
            '[*]',
            '* = TICKET_VIEW, !WIKI_VIEW',
        ]))

        results = self.search_api.query("type:ticket", context=self.context)
        self.assertEqual(results.hits, 2)
        results = self.search_api.query("type:wiki", context=self.context)
        self.assertEqual(results.hits, 0)

    def test_granular_permissions(self):
        self.write_authz_config("""
            [ticket:1]
            * = TICKET_VIEW
        """)

        results = self.search_api.query("type:ticket", context=self.context)
        self.assertEqual(results.hits, 1)
        self.assertEqual(results.docs[0]['id'], u'1')

    def test_deny_overrides_default_permissions(self):
        self._add_permission('x', 'TICKET_VIEW')
        self.write_authz_config("""
            [*]
            x = !TICKET_VIEW
        """)

        results = self.search_api.query("type:ticket", context=self.context)
        self.assertEqual(results.hits, 0)

    def test_includes_wildcard_rows_for_registred_users(self):
        self.write_authz_config("""
            [*]
            * = TICKET_VIEW
            [ticket:1]
            * = !TICKET_VIEW
        """)

        results = self.search_api.query("type:ticket", context=self.context)
        self.assertEqual(results.hits, 1)


    def test_includes_wildcard_rows_for_anonymous_users(self):
        self.req.authname='anonymous'
        self.write_authz_config("""
            [*]
            * = TICKET_VIEW
            [ticket:1]
            * = !TICKET_VIEW
        """)

        results = self.search_api.query("type:ticket", context=self.context)
        self.assertEqual(results.hits, 1)

    def test_includes_authenticated_rows_for_registred_users(self):
        self.write_authz_config("""
            [*]
            * = TICKET_VIEW
            [ticket:1]
            authenticated = !TICKET_VIEW
        """)

        results = self.search_api.query("type:ticket", context=self.context)
        self.assertEqual(results.hits, 1)

    def test_includes_named_rows_for_registred_users(self):
        self.write_authz_config("""
            [*]
            * = TICKET_VIEW
            [ticket:1]
            x = !TICKET_VIEW
        """)

        results = self.search_api.query("type:ticket", context=self.context)
        self.assertEqual(results.hits, 1)

    def test_includes_named_rows_for_anonymous_users(self):
        self.req.authname = 'anonymous'
        self.write_authz_config("""
            [*]
            * = TICKET_VIEW
            [ticket:1]
            anonymous = !TICKET_VIEW
        """)

        results = self.search_api.query("type:ticket", context=self.context)
        self.assertEqual(results.hits, 1)

    def test_understands_groups(self):
        self.write_authz_config("""
            [groups]
            admins = x

            [*]
            @admins = TICKET_VIEW

            [ticket:1]
            * = !TRAC_ADMIN
        """)

        results = self.search_api.query("type:ticket", context=self.context)
        self.assertEqual(results.hits, 1)

    def write_authz_config(self, content):
        with open(self.authz_config, 'w') as authz_config:
            authz_config.write(content)


def suite():
    return unittest.makeSuite(MultiProductSecurityTestSuite, 'test')

if __name__ == '__main__':
    unittest.main()
