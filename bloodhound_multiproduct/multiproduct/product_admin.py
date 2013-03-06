
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

"""Admin panels for product management"""

from trac.core import *
from trac.config import *
from trac.perm import PermissionSystem
from trac.admin.api import IAdminPanelProvider
from trac.ticket.admin import TicketAdminPanel, _save_config
from trac.resource import ResourceNotFound
from model import Product
from trac.util.translation import _, N_, gettext
from trac.web.chrome import Chrome, add_notice, add_warning
from multiproduct.util import ProductDelegate
from multiproduct.env import ProductEnvironment


class ProductAdminPanel(TicketAdminPanel):
    """The Product Admin Panel"""
    _type = 'products'
    _label = ('Product','Products')
    
    def get_admin_commands(self): 
        return None

    def get_admin_panels(self, req):
        if isinstance(req.perm.env, ProductEnvironment):
            return None
        return super(ProductAdminPanel, self).get_admin_panels(req)
    
    def _render_admin_panel(self, req, cat, page, product):
        req.perm.require('PRODUCT_VIEW')
        
        name = req.args.get('name')
        description = req.args.get('description','')
        prefix = req.args.get('prefix') if product is None else product
        owner = req.args.get('owner')
        keys = {'prefix':prefix}
        field_data = {'name':name,
                      'description':description,
                      'owner':owner,
                      }
        
        # Detail view?
        if product:
            prod = Product(self.env, keys)
            if req.method == 'POST':
                if req.args.get('save'):
                    req.perm.require('PRODUCT_MODIFY')
                    prod.update_field_dict(field_data)
                    prod.update()
                    add_notice(req, _('Your changes have been saved.'))
                    req.redirect(req.href.admin(cat, page))
                elif req.args.get('cancel'):
                    req.redirect(req.href.admin(cat, page))
            
            Chrome(self.env).add_wiki_toolbars(req)
            data = {'view': 'detail', 'product': prod}
        else:
            default = self.config.get('ticket', 'default_product')
            if req.method == 'POST':
                # Add Product
                if req.args.get('add') and req.args.get('prefix'):
                    req.perm.require('PRODUCT_CREATE')
                    try:
                        prod = Product(self.env, keys)
                    except ResourceNotFound:
                        prod = Product(self.env)
                        ProductDelegate.add_product(self.env, prod, keys, field_data)
                        add_notice(req,
                            _('The product "%(id)s" has been added.',
                            id=prefix))
                        req.redirect(req.href.admin(cat, page))
                    else:
                        if prod.prefix is None:
                            raise TracError(_('Invalid product id.'))
                        raise TracError(_("Product %(id)s already exists.",
                                          id=prefix))
                
                # Remove product
                elif req.args.get('remove'):
                    raise TracError(_('Product removal is not allowed!'))
                
                # Set default product
                elif req.args.get('apply'):
                    prefix = req.args.get('default')
                    if prefix and prefix != default:
                        self.log.info("Setting default product to %s",
                                      prefix)
                        self.config.set('ticket', 'default_product',
                                        prefix)
                        _save_config(self.config, req, self.log)
                        req.redirect(req.href.admin(cat, page))
            
            products = Product.select(self.env)
            data = {'view': 'list',
                    'products': products,
                    'default': default}
        if self.config.getbool('ticket', 'restrict_owner'):
            perm = PermissionSystem(self.env)
            def valid_owner(username):
                return perm.get_user_permissions(username).get('TICKET_MODIFY')
            data['owners'] = [username for username, name, email
                              in self.env.get_known_users()
                              if valid_owner(username)]
            data['owners'].insert(0, '')
            data['owners'].sort()
        else:
            data['owners'] = None
        return 'admin_products.html', data

