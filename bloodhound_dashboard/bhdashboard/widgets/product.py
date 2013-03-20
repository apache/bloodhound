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


r"""Project dashboard for Apache(TM) Bloodhound

Widgets displaying product information (multiproduct).
"""

from trac.util.translation import _
from trac.ticket.model import Milestone

from bhdashboard.util import WidgetBase, check_widget_name, pretty_wrapper

from multiproduct.env import Product, ProductEnvironment
from multiproduct.hooks import ProductizedHref


__metaclass__ = type

class ProductWidget(WidgetBase):
    """Display products available to the user.
    """
    def get_widget_params(self, name):
        """Return a dictionary containing arguments specification for
        the widget with specified name.
        """
        return {
                'max' : {
                        'desc' : """Limit the number of products displayed""",
                        'type' : int
                    },
            }

    get_widget_params = pretty_wrapper(get_widget_params, check_widget_name)

    def _get_product_milestones(self, req, product, max_):
        milestones = []
        penv = ProductEnvironment(self.env, product.prefix)
        href = ProductizedHref(self.env, penv.href.base)
        for m in Milestone.select(penv):
            m.url = href.milestone(m.name)
            m.ticket_count = penv.db_query(
                'SELECT count(*) FROM ticket WHERE milestone="%s" '
                'AND status <> "closed"' % m.name)[0][0]
            milestones.append(m)
            if len(milestones) == max_:
                break

        milestones.sort(key=lambda x: x.ticket_count, reverse=True)
        if len(milestones) == max_:
            m = Milestone(penv)
            m.name = _('... more')
            m.url = href.milestone()
            m.ticket_count = None
            milestones.append(m)

        # TODO: add a (No milestone) to the list, pointing
        # to the tickets (query) without a set milestones
        return milestones


    def render_widget(self, name, context, options):
        """Gather product list and render data in compact view
        """
        data = {}
        req = context.req
        title = ''
        params = ('max', )
        max_, = self.bind_params(name, options, *params)

        if not isinstance(req.perm.env, ProductEnvironment):
            for p in Product.select(self.env):
                if 'PRODUCT_VIEW' in req.product_perm(p.prefix):
                    p.milestones = self._get_product_milestones(req, p, max_)
                    data.setdefault('product_list', []).append(p)
            title = _('Products')

        return 'widget_product.html', \
            { 'title': title, 'data': data, }, context

    render_widget = pretty_wrapper(render_widget, check_widget_name)

