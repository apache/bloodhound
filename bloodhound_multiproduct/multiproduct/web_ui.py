
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
from multiproduct.util import ProductDelegate


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
                    # Request.args[] are lazily evaluated, so special care must be
                    # taken when creating new Requests from an old environment, as
                    # the args will be evaluated again. In case of POST requests,
                    # this comes down to re-evaluating POST parameters such as
                    # <form> arguments, which in turn causes yet another read() on
                    # a socket, causing the request to block (deadlock).
                    #
                    # The following happens during Requests.args[] evaluation:
                    #   1. Requests.callbacks['args'] is called -> arg_list_to_args(req.arg_list)
                    #   2. req.arg_list is evaluated, calling Request._parse_arg_list
                    #   3. _parse_arg_list() calls _FieldStorage() for reading the params
                    #   4. _FieldStorage() constructor calls self.read_urlencoded()
                    #   5. this calls self.fp.read() which reads from the socket
                    #
                    # Since the 'newreq' above is created from the same environ as 'req',
                    # the newreq.args below caused a re-evaluation, thus a deadlock.
                    # The fix is to copy the args from the old request to the new one.
                    setattr(newreq, 'args', req.args)
                    
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
        if req.path_info == '/products':
            return True

        # handle '/products/...', but excluding QuickCreateTicket (qct) requests
        m = PRODUCT_RE.match(req.path_info)
        return m and m.group('pathinfo').strip('/') != 'qct'
    
    def process_request(self, req):
        """process request handler"""
        
        req.perm.require('PRODUCT_VIEW')
        pid = req.args.get('productid', None)
        if pid:
            req.perm('product', pid).require('PRODUCT_VIEW')
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
                raise TracError(_('Product removal is not allowed!'))
        elif action in ('new', 'edit'):
            return self._render_editor(req, product)
        elif action == 'delete':
            raise TracError(_('Product removal is not allowed!'))
        
        if pid is None:
            data = {'products': products,
                    'context': web_context(req, Resource('products', None))}
            return 'product_list.html', data, None
        
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
                ProductDelegate.add_product(self.env, product, keys, field_data)
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
