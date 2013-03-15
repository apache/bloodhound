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

from bhdashboard.util import WidgetBase, check_widget_name, pretty_wrapper

from multiproduct.env import Product, ProductEnvironment


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

    def render_widget(self, name, context, options):
        """Gather product list and render data in compact view
        """
        data = {}
        req = context.req
        title = ''

        if not isinstance(req.perm.env, ProductEnvironment):
            data['product_list'] = [p for p in Product.select(self.env)
                if 'PRODUCT_VIEW' in req.product_perm(p.prefix)]
            title = _('Products')

        return 'widget_product.html', \
            { 'title': title, 'data': data, }, context

    render_widget = pretty_wrapper(render_widget, check_widget_name)

