
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

"""ProductModule

Provides request filtering to capture product related paths
"""

from trac.core import Component, TracError, implements
from trac.resource import Neighborhood, Resource, ResourceNotFound
from trac.util.translation import _
from trac.web.api import HTTPNotFound, IRequestHandler
from trac.web.chrome import (
    Chrome, INavigationContributor, add_link, add_notice, add_warning,
    prevnext_nav, web_context
)

from multiproduct.hooks import PRODUCT_RE
from multiproduct.model import Product


class ProductModule(Component):
    """Base Product behaviour"""

    implements(IRequestHandler)

    # IRequestHandler methods
    def match_request(self, req):
        m = PRODUCT_RE.match(req.path_info)
        if m:
            req.args['productid'] = m.group('pid')
            req.args['pathinfo'] = m.group('pathinfo')
        return not m is None

    def process_request(self, req):
        """process request handler"""

        req.perm.require('PRODUCT_VIEW')
        pid = req.args.get('productid', None)
        if pid:
            req.perm('product', pid).require('PRODUCT_VIEW')

        try:
            product = Product(self.env, {'prefix': pid})
        except ResourceNotFound:
            product = Product(self.env)

        path_info = req.args.get('pathinfo')
        if path_info and path_info != '/':
            if not product._exists:
                # bh:ticket:561 - Display product list and warning message
                if pid:
                    add_warning(req, _("Product %(pid)s not found", pid=pid))
                return self._render_list(req)
            else:
                raise HTTPNotFound(
                    _('Unable to render product page. Wrong setup?'))

        if pid:
            add_link(req, 'up', req.href.products(), _('Products'))

        action = req.args.get('action', 'view')
        if req.method == 'POST':
            if 'cancel' in req.args:
                req.redirect(req.href.products(product.prefix))
            elif action == 'edit':
                return self._do_save(req, product)
            elif action == 'delete':
                raise TracError(_('Product removal is not allowed!'))
        elif action in ('new', 'edit'):
            return self._render_editor(req, product)
        elif action == 'delete':
            raise TracError(_('Product removal is not allowed!'))

        if not product._exists:
            if pid:
                # bh:ticket:561 - Display product list and warning message
                add_warning(req, _("Product %(pid)s not found", pid=pid))
            return self._render_list(req)

        data = {'product': product,
                'context': web_context(req, product.resource)}
        return 'product_view.html', data, None

    def _render_list(self, req):
        """products list"""
        products = [p for p in Product.select(self.env)
                    if 'PRODUCT_VIEW' in req.perm(Neighborhood('product',
                                                               p.prefix))]
        data = {'products': products,
                'context': web_context(req, Resource('product', None))}
        return 'product_list.html', data, None

    def _render_editor(self, req, product):
        """common processing for creating rendering the edit page"""
        if product._exists:
            req.perm(product.resource).require('PRODUCT_MODIFY')
        else:
            req.perm(product.resource).require('PRODUCT_CREATE')
        
        chrome = Chrome(self.env)
        chrome.add_jquery_ui(req)
        chrome.add_wiki_toolbars(req)
        data = {'product': product, 
                'context': web_context(req, product.resource)}
        return 'product_edit.html', data, None
    
    def _do_save(self, req, product):
        """common processing for product save events"""
        req.perm.require('PRODUCT_VIEW')
        
        name = req.args.get('name')
        prefix = req.args.get('prefix')
        description = req.args.get('description', '')
        
        owner = req.args.get('owner') or req.authname
        keys = {'prefix': prefix}
        field_data = {'name': name,
                      'description': description,
                      'owner': owner,
                      }
        
        warnings = []
        def warn(msg):
            add_warning(req, msg)
            warnings.append(msg)
        
        if product._exists:
            if name != product.name and Product.select(self.env, 
                                                       where={'name': name}):
                warn(_('A product with name "%(name)s" already exists, please '
                       'choose a different name.', name=name))
            elif not name:
                warn(_('You must provide a name for the product.'))
            else:
                req.perm.require('PRODUCT_MODIFY')
                product.update_field_dict(field_data)
                product.update()
                add_notice(req, _('Your changes have been saved.'))
        else:
            req.perm.require('PRODUCT_CREATE')
            
            if not prefix:
                warn(_('You must provide a prefix for the product.'))
            elif Product.select(self.env, where={'prefix': prefix}):
                warn(_('Product "%(id)s" already exists, please choose another '
                       'prefix.', id=prefix))
            if not name:
                warn(_('You must provide a name for the product.'))
            elif Product.select(self.env, where={'name': name}):
                warn(_('A product with name "%(name)s" already exists, please '
                       'choose a different name.', name=name))
            
            if not warnings:
                prod = Product(self.env)
                prod.update_field_dict(keys)
                prod.update_field_dict(field_data)
                prod.insert()
                add_notice(req, _('The product "%(id)s" has been added.',
                                  id=prefix))

        if warnings:
            product.update_field_dict(keys)
            product.update_field_dict(field_data)
            return self._render_editor(req, product)
        req.redirect(req.href.products(prefix))

    # helper methods for INavigationContributor implementations
    @classmethod
    def get_product_path(cls, env, req, itempath):
        """Provide a navigation item path"""
        product = req.args.get('productid', '')
        if product and env.is_component_enabled(ProductModule):
            return req.href('products', product, itempath)
        return req.href(itempath)

    @classmethod
    def get_product_list(cls, env, req, href_fcn=None):
        """Returns a list of products as (prefix, name, url) tuples
        """
        if href_fcn is None:
            href_fcn = req.href.products
        product_list = []
        for product in Product.select(env):
            if 'PRODUCT_VIEW' in req.perm(Neighborhood('product',
                                                       product.prefix).
                                          child(product.resource)):
                product_list.append((product.prefix, product.name,
                                     href_fcn(product.prefix)))
        return product_list
