
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
import re

from genshi.builder import tag
from genshi.core import Attrs, QName

from trac.core import Component, implements, TracError
from trac.resource import Resource, ResourceNotFound
from trac.util.translation import _
from trac.web.api import IRequestFilter, IRequestHandler, Request, HTTPNotFound
from trac.web.chrome import (add_link, add_notice, add_warning, prevnext_nav,
                             Chrome, INavigationContributor, web_context)
from trac.web.main import RequestDispatcher

from multiproduct.model import Product

PRODUCT_RE = re.compile(r'^/products/(?P<pid>[^/]*)(?P<pathinfo>.*)')

class ProductModule(Component):
    """Base Product behaviour"""
    
    implements(IRequestFilter, IRequestHandler, INavigationContributor)
    NAVITEM_DO_NOT_TRANSFORM = [ '/dashboard',
                                 '/login',
                                 '/logout',
                                 '/products',
                                ]
    def get_active_navigation_item(self, req):
        return 'products'
    
    def get_navigation_items(self, req):
        if 'PRODUCT_VIEW' in req.perm:
            yield ('mainnav', 'products',
                   tag.a(_('Products'), href=req.href.products(), accesskey=3))
    
    # IRequestFilter methods
    def pre_process_request(self, req, handler):
        """pre process request filter"""
        pid = None
        match = PRODUCT_RE.match(req.path_info)
        if match:
            dispatcher = self.env[RequestDispatcher]
            if dispatcher is None:
                raise TracError('Unable to load RequestDispatcher.')
            pid = match.group('pid')
        
        if pid:
            products = Product.select(self.env, where={'prefix': pid})
            if pid and len(products) == 1:
                req.args['productid'] = pid
                req.args['product'] = products[0].name
                if handler is self and match.group('pathinfo') not in ('', '/'):
                    # select a new handler
                    environ = req.environ.copy()
                    pathinfo = environ['PATH_INFO'].split('/')
                    pathinfo = '/'.join(pathinfo[:1] + pathinfo[3:])
                    environ['PATH_INFO'] = pathinfo
                    newreq = Request(environ, lambda *args, **kwds: None)
                    
                    new_handler = None
                    for hndlr in dispatcher.handlers:
                        if hndlr is not self and hndlr.match_request(newreq):
                            new_handler = hndlr
                            req.args.update(newreq.args)
                            break
                    if new_handler is None:
                        if req.path_info.endswith('/'):
                            target = req.path_info.rstrip('/').encode('utf-8')
                            if req.query_string:
                                target += '?' + req.query_string
                            req.redirect(req.href + target, permanent=True)
                        raise HTTPNotFound('No handler matched request to %s',
                                           req.path_info)
                    handler = new_handler
            else:
                raise ResourceNotFound(_("Product %(id)s does not exist.", 
                                         id=pid), _("Invalid product id"))
        
        return handler
    
    def post_process_request(self, req, template, data, content_type):
        """post process request filter"""
        # update the nav item links
        root = req.href()
        rootproducts = req.href.products()
        pid = req.args.get('productid')
        if pid:
            for navkey, section in req.chrome['nav'].iteritems():
                for item in section:
                    try:
                        href = item['label'].attrib.get('href')
                    except AttributeError:
                        continue
                    if href.startswith(rootproducts):
                        continue
                    if href.startswith(root):
                        tail = href[len(root):]
                        if tail not in self.NAVITEM_DO_NOT_TRANSFORM:
                            attrs = [attr for attr in item['label'].attrib 
                                     if attr[0] != 'href']
                            newhref = req.href.products(pid, tail)
                            item['label'].attrib = Attrs([(QName('href'), 
                                                           newhref)] + attrs)
        
        return (template, data, content_type)
    
    # IRequestHandler methods
    def match_request(self, req):
        """match request handler"""
        if req.path_info.startswith('/products'):
            return True
        return False
    
    def process_request(self, req):
        """process request handler"""
        
        req.perm.require('PRODUCT_VIEW')
        pid = req.args.get('productid', None)
        action = req.args.get('action', 'view')
        
        products = [p for p in Product.select(self.env)
                    if 'PRODUCT_VIEW' in req.perm(p.resource)]
        
        if pid is not None:
            add_link(req, 'up', req.href.products(), _('Products'))
        
        try:
            product = Product(self.env, {'prefix': pid})
        except ResourceNotFound:
            product = Product(self.env)
        
        data = {'product': product, 
                'context': web_context(req, product.resource)}
        
        if req.method == 'POST':
            if req.args.has_key('cancel'):
                req.redirect(req.href.products(product.prefix))
            elif action == 'edit':
                return self._do_save(req, product)
            elif action == 'delete':
                req.perm(product.resource).require('PRODUCT_DELETE')
                retarget_to = req.args.get('retarget', None)
                name = product.name
                product.delete(resources_to=retarget_to)
                add_notice(req, _('The product "%(n)s" has been deleted.',
                                  n = name))
                req.redirect(req.href.products())
        elif action in ('new', 'edit'):
            return self._render_editor(req, product)
        elif action == 'delete':
            req.perm(product.resource).require('PRODUCT_DELETE')
            return 'product_delete.html', data, None
        
        if pid is None:
            data = {'products': products,
                    'context': web_context(req, Resource('products', None))}
            return 'product_list.html', data, None
        
        def add_product_link(rel, product):
            href = req.href.products(product.prefix)
            add_link(req, rel, href, _('Product "%(name)s"',
                                       name=product.name))
        
        idx = [i for i, p in enumerate(products) if p.name == product.name]
        if idx:
            idx = idx[0]
            if idx > 0:
                add_product_link('first', products[0])
                add_product_link('prev', products[idx - 1])
            if idx < len(products) - 1:
                add_product_link('next', products[idx + 1])
                add_product_link('last', products[-1])        
        prevnext_nav(req, _('Previous Product'), _('Next Product'),
                     _('Back to Product List'))
        return 'product_view.html', data, None
    
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
                'context' : web_context(req, product.resource)}
        return 'product_edit.html', data, None
    
    def _do_save(self, req, product):
        """common processing for product save events"""
        req.perm.require('PRODUCT_VIEW')
        
        name = req.args.get('name')
        prefix = req.args.get('prefix')
        description = req.args.get('description','')
        
        owner = req.args.get('owner')
        keys = {'prefix':prefix}
        field_data = {'name':name,
                      'description':description,
                      'owner':owner,
                      }
        
        warnings = []
        def warn(msg):
            add_warning(req, msg)
            warnings.append(msg)
        
        if product._exists:
            if name != product.name and Product.select(self.env, 
                                                       where={'name':name}):
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
            elif Product.select(self.env, where={'prefix':prefix}):
                warn(_('Product "%(id)s" already exists, please choose another '
                       'prefix.', id=prefix))
            if not name:
                warn(_('You must provide a name for the product.'))
            elif Product.select(self.env, where={'name':name}):
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
