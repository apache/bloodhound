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

from trac.core import Component, implements

from bhsearch.api import IDocIndexPreprocessor

from bhrelations.api import RelationsSystem, ResourceIdSerializer


class RelationsDocPreprocessor(Component):
    implements(IDocIndexPreprocessor)

    def pre_process(self, doc):
        resource_id = ':'.join([
            doc.get('product', ''), doc.get('type', ''), doc.get('id')])

        rls = RelationsSystem(self.env)
        relations = []
        for relation in rls._select_relations(resource_id):
            relations.extend(self._format_relations(relation))
        doc['relations'] = ' '.join(relations)

    def _format_relations(self, relation):
        ris = ResourceIdSerializer
        product, realm, res_id = ris.split_full_id(relation.destination)

        if realm == 'ticket':
            yield '%s:%s-%s' % (relation.type, product, res_id)
            yield '%s:#%s' % (relation.type, res_id)
        elif realm == 'wiki':
            yield '%s:%s' % (relation.type, res_id)
