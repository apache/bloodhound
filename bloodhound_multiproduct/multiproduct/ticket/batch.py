
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

from trac.ticket.batch import BatchModifyModule
from trac.util.translation import _
from trac.web.chrome import add_script_data
from multiproduct.env import ProductEnvironment


class ProductBatchModifyModule(BatchModifyModule):
    def add_template_data(self, req, data, tickets):
        if isinstance(self.env, ProductEnvironment):
            super(ProductBatchModifyModule, self).add_template_data(
                req, data, tickets)
            return

        data['batch_modify'] = True
        data['query_href'] = req.session['query_href'] or req.href.query()

        tickets_by_product = {}
        for t in tickets:
            tickets_by_product.setdefault(t['product'], []).append(t)

        data['action_controls'] = []
        global_env = ProductEnvironment.lookup_global_env(self.env)
        cache = {}
        for k,v in tickets_by_product.iteritems():
            batchmdl = cache.get(k or '')
            if batchmdl is None:
                env = ProductEnvironment(global_env, k) if k else global_env
                cache[k] = batchmdl = ProductBatchModifyModule(env)
            data['action_controls'] += batchmdl._get_action_controls(req, v)
        batch_list_modes = [
            {'name': _("add"), 'value': "+"},
            {'name': _("remove"), 'value': "-"},
            {'name': _("add / remove"), 'value': "+-"},
            {'name': _("set to"), 'value': "="},
        ]
        add_script_data(req, batch_list_modes=batch_list_modes,
                             batch_list_properties=self._get_list_fields())

import trac.ticket.batch
trac.ticket.batch.BatchModifyModule = ProductBatchModifyModule
trac.ticket.BatchModifyModule = ProductBatchModifyModule
