
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

from trac.core import Component, implements, TracError
from trac.resource import ResourceNotFound
from trac.util.translation import _
from trac.web.api import IRequestFilter, IRequestHandler, Request, HTTPNotFound
from trac.web.main import RequestDispatcher

from multiproduct.model import Product

PRODUCT_RE = re.compile(r'^/products/(?P<pid>[^/]*)(?P<pathinfo>.*)')

class ProductModule(Component):
    """Base Product behaviour"""
    
    implements(IRequestFilter, IRequestHandler)
    
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
        return (template, data, content_type)
    
    # IRequestHandler methods
    def match_request(self, req):
        """match request handler"""
        if req.path_info.startswith('/products'):
            return True
        return False
    
    def process_request(self, req):
        """process request handler"""
        if req.args.get('productid', None):
            return 'product.html', None, None
        return 'product_list.html', None, None
        