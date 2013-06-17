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
from itertools import groupby
import os

from trac.core import Component, implements, ExtensionPoint
from trac.perm import PermissionSystem
from tracopt.perm.authz_policy import AuthzPolicy
from whoosh import query

from multiproduct.env import ProductEnvironment

from bhsearch.api import (IDocIndexPreprocessor, IndexFields,
                          IQueryPreprocessor, ISearchParticipant)
from bhsearch.utils import get_product, instance_for_every_env, is_enabled


class SecurityPreprocessor(Component):
    participants = ExtensionPoint(ISearchParticipant)

    def __init__(self):
        self._required_permissions = {}
        for participant in self.participants:
            permission = participant.get_required_permission()
            doc_type = participant.get_participant_type()
            self._required_permissions[doc_type] = permission

    def check_permission(self, doc, context):
        product, doctype, id = doc['product'], doc['type'], doc['id']
        username = context.req.authname
        env = self.env
        if product:
            env = ProductEnvironment(self.env, product)
        perm = PermissionSystem(env)
        action = self._required_permissions[doctype]
        return perm.check_permission(action, username, id)

    def update_security_filter(self, query_parameters, allowed=(), denied=()):
        security_filter = self.create_security_filter(query_parameters)
        security_filter.allowed.extend(allowed)
        security_filter.denied.extend(denied)

    def create_security_filter(self, query_parameters):
        security_filter = self.find_security_filter(query_parameters['filter'])
        if not security_filter:
            security_filter = SecurityFilter()
            if query_parameters['filter']:
                query_parameters['filter'] = query.And([query_parameters['filter'],
                                                        security_filter])
            else:
                query_parameters['filter'] = security_filter
        return security_filter

    def find_security_filter(self, existing_query):
        queue = [existing_query]
        while queue:
            token = queue.pop(0)
            if isinstance(token, SecurityFilter):
                return token
            if isinstance(token, query.CompoundQuery):
                queue.extend(token.subqueries)


class DefaultSecurityPreprocessor(SecurityPreprocessor):
    implements(IDocIndexPreprocessor, IQueryPreprocessor)

    # IDocIndexPreprocessor methods
    def pre_process(self, doc):
        permission = self._required_permissions[doc[IndexFields.TYPE]]
        doc[IndexFields.REQUIRED_PERMISSION] = permission

    # IQueryPreprocessor methods
    def query_pre_process(self, query_parameters, context=None):
        if context is None:
            return

        def allowed_documents():
            #todo: add special case handling for trac_admin and product_owner
            for product, perm in self._get_all_user_permissions(context):
                if product:
                    prod_term = query.Term(IndexFields.PRODUCT, product)
                else:
                    prod_term = query.Not(query.Every(IndexFields.PRODUCT))
                perm_term = query.Term(IndexFields.REQUIRED_PERMISSION, perm)
                yield query.And([prod_term, perm_term])

        self.update_security_filter(query_parameters,
                                    allowed=allowed_documents())

    def _get_all_user_permissions(self, context):
        username = context.req.authname
        permissions = []
        for perm in instance_for_every_env(self.env, PermissionSystem):
            prefix = get_product(perm.env).prefix
            for action in self._required_permissions.itervalues():
                if perm.check_permission(action, username):
                    permissions.append((prefix, action))
        return permissions


class AuthzSecurityPreprocessor(SecurityPreprocessor):
    implements(IQueryPreprocessor)

    def __init__(self):
        SecurityPreprocessor.__init__(self)
        ps = PermissionSystem(self.env)
        self.enabled = (is_enabled(self.env, AuthzPolicy)
                        and any(isinstance(policy, AuthzPolicy)
                                for policy in ps.policies))

    # IQueryPreprocessor methods
    def query_pre_process(self, query_parameters, context=None):
        if not self.enabled:
            return

        permissions = self.get_user_permissions(context.req.authname)
        allowed_docs, denied_docs = [], []
        for product, doc_type, doc_id, perm, denied in permissions:
            term_spec = []
            if product:
                term_spec.append(query.Term(IndexFields.PRODUCT, product))
            else:
                term_spec.append(query.Not(query.Every(IndexFields.PRODUCT)))

            if doc_type != '*':
                term_spec.append(query.Term(IndexFields.TYPE, doc_type))
            if doc_id != '*':
                term_spec.append(query.Term(IndexFields.ID, doc_id))
            term_spec.append(query.Term(IndexFields.REQUIRED_PERMISSION, perm))
            term_spec = query.And(term_spec)
            if denied:
                denied_docs.append(term_spec)
            else:
                allowed_docs.append(term_spec)
        self.update_security_filter(query_parameters, allowed_docs, denied_docs)

    def get_user_permissions(self, username):
        for policy in instance_for_every_env(self.env, AuthzPolicy):
            product = get_product(policy.env).prefix
            self.refresh_config(policy)

            for doc_type, doc_id, perm, denied in self.get_relevant_permissions(policy, username):
                yield product, doc_type, doc_id, perm, denied

    def get_relevant_permissions(self, policy, username):
        ps = PermissionSystem(self.env)
        relevant_permissions = set(self._required_permissions.itervalues())
        user_permissions = self.get_all_user_permissions(policy, username)
        for doc_type, doc_id, permissions in user_permissions:
            for deny, perms in groupby(permissions,
                                       key=lambda p: p.startswith('!')):
                if deny:
                    for p in ps.expand_actions([p[1:] for p in perms]):
                        if p in relevant_permissions:
                            yield doc_type, doc_id, p, True
                else:
                    for p in ps.expand_actions(perms):
                        if p in relevant_permissions:
                            yield doc_type, doc_id, p, False

    def get_all_user_permissions(self, policy, username):
        relevant_users = self.get_relevant_users(username)
        for doc_type, doc_id, section in self.get_all_permissions(policy):
            for who, permissions in section.iteritems():
                if who in relevant_users or \
                        who in policy.groups_by_user.get(username, []):
                    if isinstance(permissions, basestring):
                        permissions = [permissions]
                    yield doc_type, doc_id, permissions

    def get_all_permissions(self, policy):
        for section_name in policy.authz.sections:
            if section_name == 'groups':
                continue
            if '/' in section_name:
                continue  # advanced permissions are not supported at the moment

            type_id = section_name.split('@', 1)[0]
            if ':' in type_id:
                doc_type, doc_id = type_id.split(':')
            else:
                doc_type, doc_id = '**'
            yield doc_type, doc_id, policy.authz[section_name]

    def get_relevant_users(self, username):
        if username and username != 'anonymous':
            return ['*', 'authenticated', username]
        else:
            return ['*', 'anonymous']

    def refresh_config(self, policy):
        if (
            policy.authz_file and not policy.authz_mtime
            or os.path.getmtime(policy.get_authz_file()) > policy.authz_mtime
        ):
            policy.parse_authz()


class SecurityFilter(query.AndNot):
    def __init__(self, allowed=(), denied=()):
        self.allowed = list(allowed)
        self.denied = list(denied)
        super(SecurityFilter, self).__init__(self.allowed, self.denied)

    _subqueries = ()
    @property
    def subqueries(self):
        self.finalize()
        return self._subqueries

    @subqueries.setter
    def subqueries(self, value):
        pass

    def finalize(self):
        self._subqueries = []
        if self.allowed:
            self.a = query.Or(self.allowed)
        else:
            self.a = query.NullQuery
        if self.denied:
            self.b = query.Or(self.denied)
        else:
            self.b = query.NullQuery
        self._subqueries = (self.a, self.b)

    def __repr__(self):
        r = "%s(allow=%r, deny=%r)" % (self.__class__.__name__,
                                       self.a, self.b)
        return r
