
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
from trac.ticket.model import Ticket
from trac.ticket.web_ui import TicketModule
from trac.web.api import Request, IRequestFilter, ITemplateStreamFilter
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
    implements(IRequestFilter)

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


