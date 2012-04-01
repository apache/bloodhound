
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

from genshi.builder import tag
from genshi.core import Markup, Stream, TEXT
from genshi.filters import Transformer
from genshi.input import HTML
from trac.core import *
from trac.ticket.api import TicketSystem
from trac.ticket.model import Ticket
from trac.ticket.web_ui import TicketModule
from trac.web.api import Request, IRequestFilter, IRequestHandler
from trac.web.chrome import Chrome
from trac.web.main import RequestDispatcher

from themeengine.api import ThemeBase

from urlparse import urlparse
from wsgiref.util import setup_testing_defaults

def dummy_request(env, uname=None):
    environ = {}
    setup_testing_defaults(environ)
    environ.update({
                'REQUEST_METHOD' : 'GET',
                'SCRIPT_NAME' : urlparse(str(env._abs_href())).path,
                'trac.base_url' : str(env._abs_href()), 
                })
    req = Request(environ, lambda *args, **kwds: None)
    # Intercept redirection
    req.redirect = lambda *args, **kwds: None
    # Setup user information
    if uname is not None :
      environ['REMOTE_USER'] = req.authname = uname
    
    rd = RequestDispatcher(env)
    chrome = Chrome(env)
    req.callbacks.update({
        'authname': rd.authenticate,
        'chrome': chrome.prepare_request,
        'hdf': getattr(rd, '_get_hdf', None),
        'locale' : getattr(rd, '_get_locale', None),
        'perm': rd._get_perm,
        'session': rd._get_session,
        'tz': rd._get_timezone,
        'form_token': rd._get_form_token
    })
    return req

class BloodhoundTheme(ThemeBase):
    """Look and feel of Bloodhound issue tracker.
    """
    template = htdocs = css = screenshot = True

    # Internal methods
    def is_theme_active(self, req):
        # TODO: Implement
        return True

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
        if (template, data, content_type) != (None,) * 3: # TODO: Check !
            if data is None:
                data = {}
            fakereq = dummy_request(self.env)
            ticket = Ticket(self.env)
            tm = TicketModule(self.env)
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
            tm = self.env[TicketModule]
            if tm is None:
                raise TracError('Unable to load TicketModule (disabled)?')
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


