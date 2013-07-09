import re
import pkg_resources

from trac.core import *
from trac.web.chrome import ITemplateProvider
from trac.web.main import IRequestHandler
from trac.perm import IPermissionRequestor, PermissionCache, PermissionSystem
from trac.util import escape, Markup
from trac.core import Component, implements
from trac.ticket import model
from trac.core import TracError
from trac.ticket.model import Ticket, Milestone
from trac.ticket.web_ui import TicketModule
from trac.ticket.api import TicketSystem
from multiproduct.model import Product
from multiproduct.web_ui import ProductModule
from trac.resource import Resource, ResourceNotFound


class EmbeddingSystem(Component):
    implements(IRequestHandler, IPermissionRequestor, ITemplateProvider)


    # IPermissionRequestor method
    def get_permission_actions(self):
        return ['TICKET_VIEW', 'MILESTONE_VIEW', 'PRODUCT_VIEW']


    # IRequestHandler methods
    def match_request(self, req):
        embed_re = re.compile(r'^/api/(?P<resource_name>[^/]*)/(?P<resource_key>[^/]*)$')
        match = embed_re.match(req.path_info)

        if match:
            req.args['resource_name'] = match.group('resource_name')
            req.args['resource_key'] = match.group('resource_key')
        return not match is None


    def process_request(self, req):
        resource = req.args.get('resource_name')
        key = req.args.get('resource_key')

        if resource == 'ticket':
            req.perm.require('TICKET_MODIFY')
            data = {'ticket': Ticket(self.env, key)}
            return 'bh_emb_ticket.html', data, None
        elif resource == 'milestone':
            req.perm.require('MILESTONE_MODIFY')
            data = {'milestone': Milestone(self.env, key)}
            return 'bh_emb_milestone.html', data, None
        elif resource == 'products':
            req.perm.require('PRODUCT_MODIFY')
            data = {'product': Product(self.env, {'prefix': key})}
            return 'bh_emb_product.html', data, None
        else:
            msg = "Resource does not exist."
            raise ResourceNotFound((msg), ("Invalid resource"))

# Check for when the fields are not filled in

    ### ITemplateProvider methods

    def get_templates_dirs(self):
        resource_filename = pkg_resources.resource_filename
        return [resource_filename('bhembedding', 'templates')]

    def get_htdocs_dirs(self):
        return [] # temporarily, since there are no html docs yet
        # from pkg_resources import resource_filename
        # return [('ticket', resource_filename('bhembedding', 'htdocs'))]
