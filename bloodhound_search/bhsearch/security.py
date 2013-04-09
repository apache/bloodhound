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

from trac.core import Component, implements, ExtensionPoint
from trac.perm import PermissionSystem
from whoosh import query

from bhsearch.api import (IDocIndexPreprocessor, IndexFields,
                          IQueryPreprocessor, ISearchParticipant)
from bhsearch.utils import get_product, instance_for_every_env


class SecurityPreprocessor(Component):
    implements(IDocIndexPreprocessor, IQueryPreprocessor)

    participants = ExtensionPoint(ISearchParticipant)

    def __init__(self):
        self._required_permissions = {}
        for participant in self.participants:
            permission = participant.get_required_permission()
            doc_type = participant.get_participant_type()
            self._required_permissions[doc_type] = permission

    # IDocIndexPreprocessor methods
    def pre_process(self, doc):
        permission = self._required_permissions[doc[IndexFields.TYPE]]
        if doc.get(IndexFields.PRODUCT, ''):
            doc[IndexFields.SECURITY] = '%s/%s' % (doc[IndexFields.PRODUCT],
                                                   permission)
        else:
            doc[IndexFields.SECURITY] = permission

    # IQueryPreprocessor methods
    def query_pre_process(self, query_parameters, context=None):
        if context is None:
            return

        permissions = self._get_all_user_permissions(context)
        #todo: add special case handling for trac_admin and product_owner
        if permissions:
            security_filter = query.Or([query.Term('security', perm)
                                        for perm in permissions])
        else:
            security_filter = query.NullQuery
        if query_parameters['filter'] is None:
            query_parameters['filter'] = security_filter
        else:
            original_filters = query_parameters['filter']
            query_parameters['filter'] = query.And(
                [original_filters, security_filter])

    def _get_all_user_permissions(self, context):
        username = context.req.authname
        permissions = []
        for perm in instance_for_every_env(self.env, PermissionSystem):
            prefix = get_product(perm.env).prefix
            for action in self._required_permissions.itervalues():
                if perm.check_permission(action, username):
                    permissions.append(
                        '%s/%s' % (prefix, action) if prefix else action
                    )
        return permissions
