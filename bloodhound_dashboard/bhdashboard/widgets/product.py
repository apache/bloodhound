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

import itertools

from genshi.builder import tag

from trac.resource import Neighborhood
from trac.util.translation import _
from trac.ticket.model import Milestone, Component, Version
from trac.ticket.query import Query

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
        return {'max' : {'desc' : """Limit the number of products displayed""",
                         'type' : int},
                'cols' : {'desc' : """Number of columns""",
                          'type' : int}
                }

    get_widget_params = pretty_wrapper(get_widget_params, check_widget_name)

    def _get_product_info(self, product, resource, max_):
        penv = ProductEnvironment(self.env, product.prefix)
        href = ProductizedHref(self.env, penv.href.base)
        results = []

        # some queries return a list/tuple, some a generator,
        # hence count() to get the result length
        def count(iter_):
            try:
                return len(iter_)
            except TypeError:
                return sum(1 for _ in iter_)

        query = resource['type'].select(penv)
        for q in itertools.islice(query, max_):
            q.url = href(resource['name'], q.name) if resource.get('hrefurl') \
                else Query.from_string(penv, 'order=priority&%s=%s' %
                    (resource['name'], q.name)).get_href(href)
            q.ticket_count = penv.db_query(
                """SELECT COUNT(*) FROM ticket WHERE ticket.%s='%s'
                   AND ticket.status <> 'closed'""" % (resource['name'], q.name))[0][0]

            results.append(q)

        # add a '(No <milestone/component/version>)' entry if there are
        # tickets without an assigned resource in the product
        ticket_count = penv.db_query(
            """SELECT COUNT(*) FROM ticket WHERE %s=''
               AND status <> 'closed'""" % (resource['name'],))[0][0]
        if ticket_count != 0:
            q = resource['type'](penv)
            q.name = '(No %s)' % (resource['name'],)
            q.url = Query.from_string(penv,
                        'status=!closed&col=id&col=summary&col=owner'
                        '&col=status&col=priority&order=priority&%s=' %
                        (resource['name'],)).get_href(href)
            q.ticket_count = ticket_count
            results.append(q)

        results.sort(key=lambda x: x.ticket_count, reverse=True)

        # add a link to the resource list if there are
        # more than max resources defined
        if count(query) > max_:
            q = resource['type'](penv)
            q.name = _('... more')
            q.ticket_count = None
            q.url = href(resource['name']) if resource.get('hrefurl') \
                else href.product(product.prefix)
            results.append(q)

        return results

    def render_widget(self, name, context, options):
        """Gather product list and render data in compact view
        """
        data = {}
        req = context.req
        title = ''
        params = ('max', 'cols')
        max_, cols = self.bind_params(name, options, *params)

        if not isinstance(req.perm.env, ProductEnvironment):
            for p in Product.select(self.env):
                if 'PRODUCT_VIEW' in req.perm(Neighborhood('product', p.prefix)):
                    for resource in (
                        { 'type': Milestone, 'name': 'milestone', 'hrefurl': True },
                        { 'type': Component, 'name': 'component' },
                        { 'type': Version, 'name': 'version' },
                    ):
                        setattr(p, resource['name'] + 's',
                            self._get_product_info(p, resource, max_))
                    p.owner_link = Query.from_string(self.env, 'status!=closed&'
                        'col=id&col=summary&col=owner&col=status&col=priority&'
                        'order=priority&group=product&owner=%s'
                        % (p._data['owner'] or '', )).get_href(req.href)
                    data.setdefault('product_list', []).append(p)
            title = _('Products')

        data['colseq'] = itertools.cycle(xrange(cols - 1, -1, -1)) if cols \
                         else itertools.repeat(1)

        return 'widget_product.html', \
            {
                'title': title,
                'data': data,
                'ctxtnav' : [
                    tag.a(_('More'), 
                    href = context.req.href('products'))],
            }, \
            context

    render_widget = pretty_wrapper(render_widget, check_widget_name)

