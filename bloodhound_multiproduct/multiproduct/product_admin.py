
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

from trac.admin.api import IAdminCommandProvider, AdminCommandError,\
    AdminCommandManager
from trac.admin.console import TracAdmin, TRAC_VERSION
from trac.admin.web_ui import AdminModule
from trac.core import *
from trac.config import *
from trac.perm import PermissionSystem
from trac.resource import ResourceNotFound
from trac.ticket.admin import TicketAdminPanel, _save_config
from trac.util import lazy
from trac.util.text import print_table, to_unicode, printerr, printout
from trac.util.translation import _, N_, gettext, ngettext
from trac.web.api import HTTPNotFound, IRequestFilter, IRequestHandler
from trac.web.chrome import Chrome, add_notice, add_warning

from multiproduct.env import ProductEnvironment
from multiproduct.model import Product
from multiproduct.perm import sudo

import multiproduct.versioncontrol
import trac.versioncontrol.admin
from trac.versioncontrol import DbRepositoryProvider, RepositoryManager
from multiproduct.util import ReplacementComponent

#--------------------------
# Product admin panel
#--------------------------

class ProductAdminPanel(TicketAdminPanel):
    """The Product Admin Panel"""
    _type = 'products'
    _label = ('Product','Products')
    
    def get_admin_commands(self): 
        if not isinstance(self.env, ProductEnvironment):
            yield ('product add', '<prefix> <owner> <name>',
                   'Add a new product',
                   None, self._do_product_add)
            yield ('product chown', '<prefix> <owner>',
                   'Change product ownership',
                   self._complete_product, self._do_product_chown)
            yield ('product list', '',
                   'Show available products',
                   None, self._do_product_list)
            yield ('product remove', '<prefix>',
                   'Remove/uninstall a product',
                   self._complete_product, self._do_product_remove)
            yield ('product rename', '<prefix> <newname>',
                   'Rename a product',
                   self._complete_product, self._do_product_rename)

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
                    if not owner:
                        add_warning(req, _('All fields are required!'))
                        req.redirect(req.href.admin(cat, page))

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

    def load_product(self, prefix):
        products = Product.select(self.env, where={'prefix' : prefix})
        if not products:
            raise AdminCommandError('Unknown product %s' % (prefix,))
        return products[0]

    def _complete_product(self, args):
        if len(args) == 1:
            return get_products(self.env)

    def _do_product_add(self, prefix, owner, name):
        product = Product(self.env)
        product._data.update({'prefix':prefix, 'name':name, 'owner':owner})
        try:
            product.insert()
        except TracError, exc:
            raise AdminCommandError(to_unicode(exc))

    def _do_product_chown(self, prefix, owner):
        product = self.load_product(prefix)
        product._data['owner'] = owner
        product.update()

    def _do_product_list(self):
        if not isinstance(self.env, ProductEnvironment):
            print_table([(p.prefix, p.owner, p.name)
                         for p in Product.select(self.env)],
                        [_('Prefix'), _('Owner'), _('Name')])

    def _do_product_remove(self, prefix):
        raise AdminCommandError(_("Command 'product remove' not supported yet"))

    def _do_product_rename(self, prefix, newname):
        product = self.load_product(prefix)
        product._data['name'] = newname
        product.update()


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
    implements(IAdminCommandProvider, IRequestFilter, IRequestHandler)

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

    # IAdminCommandProvider methods
    def get_admin_commands(self):
        if not isinstance(self.env, ProductEnvironment):
            yield ('product admin', '<PREFIX> <admin command>',
                   'Execute admin (sub-)command upon product resources',
                   self._complete_product_admin, self._do_product_admin)

    def product_admincmd_mgr(self, prefix):
        try:
            product_env = ProductEnvironment.lookup_env(self.env, prefix)
        except LookupError:
            raise AdminCommandError('Unknown product %s' % (prefix,))
        else:
            return AdminCommandManager(product_env)

    def _complete_product_admin(self, args):
        if len(args) == 1:
            return get_products(self.env)
        else:
            mgr = self.product_admincmd_mgr(args[0])
            return mgr.complete_command(args[1:])

    GLOBAL_COMMANDS = ('deploy', 'help', 'hotcopy', 'initenv', 'upgrade')

    def _do_product_admin(self, prefix, *args):
        mgr = self.product_admincmd_mgr(prefix)
        if args and args[0] in self.GLOBAL_COMMANDS:
            raise AdminCommandError('%s command not supported for products' %
                                    (args[0],))
        if args and args[0] == 'help':
            help_args = args[1:]
            if help_args:
                doc = mgr.get_command_help(list(help_args))
                if doc:
                    TracAdmin.print_doc(doc)
                else:
                    printerr(_("No documentation found for '%(cmd)s'."
                               " Use 'help' to see the list of commands.",
                               cmd=' '.join(help_args)))
                    cmds = mgr.get_similar_commands(help_args[0])
                    if cmds:
                        printout('')
                        printout(ngettext("Did you mean this?",
                                          "Did you mean one of these?",
                                          len(cmds)))
                        for cmd in cmds:
                            printout('    ' + cmd)
            else:
                printout(_("trac-admin - The Trac Administration Console "
                           "%(version)s", version=TRAC_VERSION))
                env = mgr.env
                TracAdmin.print_doc(TracAdmin.all_docs(env), short=True)
        else:
            mgr.execute_command(*args)

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


def get_products(env):
    return [p.prefix for p in Product.select(env)]


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


class ProductRepositoryAdminPanel(ReplacementComponent, trac.versioncontrol.admin.RepositoryAdminPanel):
    """Web admin panel for repository administration, product-aware."""

    implements(trac.admin.IAdminPanelProvider)

    # IAdminPanelProvider methods

    def get_admin_panels(self, req):
        if 'VERSIONCONTROL_ADMIN' in req.perm:
            yield ('versioncontrol', _('Version Control'), 'repository',
                   _('Repository Links') if isinstance(self.env, ProductEnvironment)
                    else _('Repositories'))

    def render_admin_panel(self, req, category, page, path_info):
        if not isinstance(self.env, ProductEnvironment):
            return super(ProductRepositoryAdminPanel, self).render_admin_panel(
                req, category, page, path_info)

        req.perm.require('VERSIONCONTROL_ADMIN')
        db_provider = self.env[DbRepositoryProvider]

        if req.method == 'POST' and db_provider:
            if req.args.get('remove'):
                repolist = req.args.get('sel')
                if repolist:
                    if isinstance(repolist, basestring):
                        repolist = [repolist, ]
                    for reponame in repolist:
                        db_provider.unlink_product(reponame)
            elif req.args.get('addlink') is not None and db_provider:
                reponame = req.args.get('repository')
                db_provider.link_product(reponame)
            req.redirect(req.href.admin(category, page))

        # Retrieve info for all product repositories
        rm_product = RepositoryManager(self.env)
        rm_product.reload_repositories()
        all_product_repos = rm_product.get_all_repositories()
        repositories = dict((reponame, self._extend_info(
                                reponame, info.copy(), True))
                            for (reponame, info) in
                                all_product_repos.iteritems())
        types = sorted([''] + rm_product.get_supported_types())

        # construct a list of all repositores not linked to this product
        rm = RepositoryManager(self.env.parent)
        all_repos = rm.get_all_repositories()
        unlinked_repositories = dict([(k, all_repos[k]) for k in
            sorted(set(all_repos) - set(all_product_repos))])

        data = {'types': types, 'default_type': rm_product.repository_type,
                'repositories': repositories,
                'unlinked_repositories': unlinked_repositories}
        return 'repository_links.html', data

trac.versioncontrol.admin.RepositoryAdminPanel = ProductRepositoryAdminPanel


