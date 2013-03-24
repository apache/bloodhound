
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

from trac.admin.api import IAdminPanelProvider
from trac.admin.web_ui import AdminModule
from trac.core import *
from trac.config import *
from trac.perm import PermissionSystem
from trac.resource import ResourceNotFound
from trac.ticket.admin import TicketAdminPanel, _save_config
from trac.util import lazy
from trac.util.translation import _, N_, gettext
from trac.web.api import HTTPNotFound, IRequestFilter, IRequestHandler
from trac.web.chrome import Chrome, add_notice, add_warning

from multiproduct.env import ProductEnvironment
from multiproduct.model import Product
from multiproduct.perm import sudo

#--------------------------
# Product admin panel
#--------------------------

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
                        prod.update_field_dict(keys)
                        prod.update_field_dict(field_data)
                        prod.insert()
                        add_notice(req, _('The product "%(id)s" has been added.',
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

#--------------------------
# Advanced administration in product context
#--------------------------

class IProductAdminAclContributor(Interface):
    """Interface implemented by components contributing with entries to the
    access control white list in order to enable admin panels in product
    context. 
    
    **Notice** that deny entries configured by users in the blacklist
    (i.e. using TracIni `admin_blacklist` option in `multiproduct` section)
    will override these entries.
    """
    def enable_product_admin_panels():
        """Return a sequence of `(cat_id, panel_id)` tuples that will be
        enabled in product context unless specified otherwise in configuration.
        If `panel_id` is set to `'*'` then all panels in section `cat_id`
        will have green light.
        """


class ProductAdminModule(Component):
    """Leverage administration panels in product context based on the
    combination of white list and black list.
    """
    implements(IRequestFilter, IRequestHandler)

    acl_contributors = ExtensionPoint(IProductAdminAclContributor)

    raw_blacklist = ListOption('multiproduct', 'admin_blacklist', 
        doc="""Do not show any product admin panels in this list even if
        allowed by white list. Value must be a comma-separated list of
        `cat:id` strings respectively identifying the section and identifier
        of target admin panel. Empty values of `cat` and `id` will be ignored
        and warnings emitted if TracLogging is enabled. If `id` is set
        to `*` then all panels in `cat` section will be added to blacklist
        while in product context.""")

    @lazy
    def acl(self):
        """Access control table based on blacklist and white list.
        """
        # FIXME : Use an immutable (mapping?) type
        acl = {}
        if isinstance(self.env, ProductEnvironment):
            for acl_c in self.acl_contributors:
                for cat_id, panel_id in acl_c.enable_product_admin_panels():
                    if cat_id and panel_id:
                        if panel_id == '*':
                            acl[cat_id] = True
                        else:
                            acl[(cat_id, panel_id)] = True
                    else:
                        self.log.warning('Invalid panel %s in white list',
                                         panel_id)
    
            # Blacklist entries will override those in white list
            warnings = []
            for panelref in self.raw_blacklist:
                try:
                    cat_id, panel_id = panelref.split(':')
                except ValueError:
                    cat_id = panel_id = ''
                if cat_id and panel_id:
                    if panel_id == '*':
                        acl[cat_id] = False
                    else:
                        acl[(cat_id, panel_id)] = False
                else:
                    warnings.append(panelref)
            if warnings:
                self.log.warning("Invalid panel descriptors '%s' in blacklist",
                                 ','.join(warnings))
        return acl

    # IRequestFilter methods
    def pre_process_request(self, req, handler):
        """Intercept admin requests in product context if `TRAC_ADMIN`
        expectations are not met.
        """
        if isinstance(self.env, ProductEnvironment) and \
                handler is AdminModule(self.env) and \
                not req.perm.has_permission('TRAC_ADMIN') and \
                req.perm.has_permission('PRODUCT_ADMIN'):
            # Intercept admin request
            return self
        return handler

    def post_process_request(self, req, template, data, content_type):
        return template, data, content_type

    # IRequestHandler methods
    def match_request(self, req):
        """Never match a request"""

    def process_request(self, req):
        """Anticipate permission error to hijack admin panel dispatching
        process in product context if `TRAC_ADMIN` expectations are not met.
        """
        # TODO: Verify `isinstance(self.env, ProductEnvironment)` once again ?
        cat_id = req.args.get('cat_id')
        panel_id = req.args.get('panel_id')
        if self._check_panel(cat_id, panel_id):
            with sudo(req):
                return self.global_process_request(req)
        else:
            raise HTTPNotFound(_('Unknown administration panel'))

    global_process_request = AdminModule.process_request.im_func

    # Internal methods
    def _get_panels(self, req):
        if isinstance(self.env, ProductEnvironment):
            panels, providers = AdminModule(self.env)._get_panels(req)
            # Filter based on ACLs
            panels = [p for p in panels if self._check_panel(p[0], p[2])]
#            providers = dict([k, p] for k, p in providers.iteritems()
#                                    if self._check_panel(*k))
            return panels, providers
        else:
            return [], []

    def _check_panel(self, cat_id, panel_id):
        cat_allow = self.acl.get(cat_id)
        panel_allow = self.acl.get((cat_id, panel_id))
        return cat_allow is not False and panel_allow is not False \
               and (cat_allow, panel_allow) != (None, None) \
               and (cat_id, panel_id) != ('general', 'plugin') # double-check !


class DefaultProductAdminWhitelist(Component):
    implements(IProductAdminAclContributor)

    # IProductAdminAclContributor methods
    def enable_product_admin_panels(self):
        yield 'general', 'basics'
        yield 'general', 'perm'
        yield 'accounts', 'notification'
        # FIXME: Include users admin panel ?
        #yield 'accounts', 'users'
        yield 'ticket', '*'
        yield 'versioncontrol', 'repository'
