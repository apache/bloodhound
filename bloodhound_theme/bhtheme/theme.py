
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

from trac.core import *
from trac.ticket.api import TicketSystem
from trac.ticket.model import Ticket
from trac.ticket.web_ui import TicketModule
from trac.util.translation import _
from trac.web.api import IRequestFilter, IRequestHandler
from trac.web.chrome import add_stylesheet, ITemplateProvider, prevnext_nav

from themeengine.api import ThemeBase, ThemeEngineSystem

from bhdashboard.util import dummy_request
from bhdashboard.web_ui import DashboardModule

from urlparse import urlparse
from wsgiref.util import setup_testing_defaults

try:
    from multiproduct.ticket.web_ui import ProductTicketModule
except ImportError:
    ProductTicketModule = None

class BloodhoundTheme(ThemeBase):
    """Look and feel of Bloodhound issue tracker.
    """
    template = htdocs = css = screenshot = disable_trac_css = True
    disable_all_trac_css = True
    BLOODHOUND_KEEP_CSS = set(
        (
            'diff.css',
        )
    )
    BLOODHOUND_TEMPLATE_MAP = {
        # Admin
        'admin_basics.html' : ('bh_admin_basics.html', None),
        'admin_components.html' : ('bh_admin_components.html', None),
        'admin_enums.html' : ('bh_admin_enums.html', None),
        'admin_logging.html' : ('bh_admin_logging.html', None),
        'admin_milestones.html' : ('bh_admin_milestones.html', None),
        'admin_perms.html' : ('bh_admin_perms.html', None),
        'admin_plugins.html' : ('bh_admin_plugins.html', None),
        'admin_repositories.html' : ('bh_admin_repositories.html', None),
        'admin_versions.html' : ('bh_admin_versions.html', None),

        # Search
        'search.html' : ('bh_search.html', '_modify_search_data'),

        # Wiki
        'wiki_delete.html' : ('bh_wiki_delete.html', None),
        'wiki_diff.html' : ('bh_wiki_diff.html', None),
        'wiki_edit.html' : ('bh_wiki_edit.html', None),
        'wiki_rename.html' : ('bh_wiki_rename.html', None),
        'wiki_view.html' : ('bh_wiki_view.html', '_modify_wiki_page_path'),

        # Ticket
        'milestone_edit.html' : ('bh_milestone_edit.html', None),
        'milestone_view.html' : ('bh_milestone_view.html', '_modify_roadmap_css'),
        'report_delete.html' : ('bh_report_delete.html', None),
        'report_edit.html' : ('bh_report_edit.html', None), 
        'report_list.html' : ('bh_report_list.html', None),
        'report_view.html' : ('bh_report_view.html', None),
        'ticket.html' : ('bh_ticket.html', None),

        # General purpose
        'history_view.html' : ('bh_history_view.html', None),
    }

    implements(IRequestFilter, ITemplateProvider)

    # IRequestFilter methods

    def pre_process_request(self, req, handler):
        """Pre process request filter"""
        return handler

    def post_process_request(self, req, template, data, content_type):
        """Post process request filter.
        Removes all trac provided css if required"""
        def is_active_theme():
            is_active = False
            active_theme = ThemeEngineSystem(self.env).theme
            if active_theme is not None:
                this_theme_name = self.get_theme_names().next()
                is_active = active_theme['name'] == this_theme_name
            return is_active
        
        is_active_theme = is_active_theme()
        if self.disable_all_trac_css and is_active_theme:
            if self.disable_all_trac_css:
                links = req.chrome.get('links',{})
                stylesheets = links.get('stylesheet',[])
                if stylesheets:
                    path = req.base_path + '/chrome/common/css/'
                    _iter = ([ss, ss.get('href', '')] for ss in stylesheets)
                    links['stylesheet'] = [ss for ss, href in _iter 
                            if not href.startswith(path) or
                            href.rsplit('/', 1)[-1] in self.BLOODHOUND_KEEP_CSS]
            template, modifier = self.BLOODHOUND_TEMPLATE_MAP.get(
                    template, (template, None))
            if modifier is not None:
                modifier = getattr(self, modifier)
                modifier(req, template, data, content_type, is_active_theme)
        return template, data, content_type

    # ITemplateProvider methods

    def get_htdocs_dirs(self):
        """Ensure dashboard htdocs will be there even if
        `bhdashboard.web_ui.DashboardModule` is disabled.
        """
        if not self.env.is_component_enabled(DashboardModule):
            return DashboardModule(self.env).get_htdocs_dirs()

    def get_templates_dirs(self):
        """Ensure dashboard templates will be there even if
        `bhdashboard.web_ui.DashboardModule` is disabled.
        """
        if not self.env.is_component_enabled(DashboardModule):
            return DashboardModule(self.env).get_templates_dirs()

    # Request modifiers

    def _modify_search_data(self, req, template, data, content_type, is_active):
        """Insert breadcumbs and context navigation items in search web UI
        """
        if is_active:
            # Insert query string in search box (see bloodhound_theme.html)
            req.search_query = data.get('query')
            # Breadcrumbs nav
            data['resourcepath_template'] = 'bh_path_search.html'
            # Context nav
            prevnext_nav(req, _('Previous'), _('Next'))

    def _modify_wiki_page_path(self, req, template, data, content_type, is_active):
        """Override wiki breadcrumbs nav items
        """
        if is_active:
            data['resourcepath_template'] = 'bh_path_wikipage.html'

    def _modify_roadmap_css(self, req, template, data, content_type, is_active):
        """Insert roadmap.css
        """
        add_stylesheet(req, 'dashboard/roadmap.css')

class QuickCreateTicketDialog(Component):
    implements(IRequestFilter, IRequestHandler)

    # IRequestFilter(Interface):

    def pre_process_request(self, req, handler):
        """Nothing to do.
        """
        return handler

    def post_process_request(self, req, template, data, content_type):
        """Append necessary ticket data
        """
        try:
            tm = self._get_ticket_module()
        except TracError:
            # no ticket module so no create ticket button
            return template, data, content_type

        if (template, data, content_type) != (None,) * 3: # TODO: Check !
            if data is None:
                data = {}
            fakereq = dummy_request(self.env)
            ticket = Ticket(self.env)
            tm._populate(fakereq, ticket, False)
            fields = dict([f['name'], f] \
                        for f in tm._prepare_fields(fakereq, ticket))
            data['qct'] = { 'fields' : fields }
        return template, data, content_type

    # IRequestHandler methods

    def match_request(self, req):
        """Handle requests sent to /qct
        """
        return req.path_info == '/qct'

    def process_request(self, req):
        """Forward new ticket request to `trac.ticket.web_ui.TicketModule`
        but return plain text suitable for AJAX requests.
        """
        try:
            tm = self._get_ticket_module()
            req.perm.require('TICKET_CREATE')
            summary = req.args.pop('field_summary', '')
            desc = ",, ... via ''Bloodhound'' quick create ticket dialog,,"
            attrs = dict([k[6:], v] for k,v in req.args.iteritems() \
                                    if k.startswith('field_'))
            ticket_id = self.create(req, summary, desc, attrs, False)
        except Exception, exc:
            self.log.exception("BH: Quick create ticket failed %s" % (exc,))
            req.send(str(exc), 'plain/text', 500)
        else:
            req.send(str(ticket_id), 'plain/text')

    def _get_ticket_module(self):
        ptm = None
        if ProductTicketModule is not None:
            ptm = self.env[ProductTicketModule]
        tm = self.env[TicketModule]
        if not (tm is None) ^ (ptm is None):
            raise TracError('Unable to load TicketModule (disabled)?')
        if tm is None:
            tm = ptm
        return tm

    # Public API
    def create(self, req, summary, description, attributes = {}, notify=False):
        """ Create a new ticket, returning the ticket ID. 

        PS: Borrowed from XmlRpcPlugin.
        """
        t = Ticket(self.env)
        t['summary'] = summary
        t['description'] = description
        t['reporter'] = req.authname
        for k, v in attributes.iteritems():
            t[k] = v
        t['status'] = 'new'
        t['resolution'] = ''
        t.insert()
        # Call ticket change listeners
        ts = TicketSystem(self.env)
        for listener in ts.change_listeners:
            listener.ticket_created(t)
        if notify:
            try:
                tn = TicketNotifyEmail(self.env)
                tn.notify(t, newticket=True)
            except Exception, e:
                self.log.exception("Failure sending notification on creation "
                                   "of ticket #%s: %s" % (t.id, e))
        return t.id


