import re
import pkg_resources

from trac.core import *
from trac.web.chrome import ITemplateProvider
from trac.web.main import IRequestHandler
from trac.perm import IPermissionRequestor
from trac.util import escape, Markup
from trac.core import Component, implements
from trac.ticket import model
from trac.core import TracError
from trac.ticket.model import Ticket
from trac.ticket.web_ui import TicketModule
from trac.ticket.api import TicketSystem


TICKET_RE = re.compile(r'^/products(?:/(?P<pid>[^/]*)/api/ticket/)([0-9]+)$')

class EmbeddingSystem(Component):
    implements(IRequestHandler, IPermissionRequestor, ITemplateProvider)


    # IPermissionRequestor method
    def get_permission_actions(self):
        return ['TICKET_MODIFY']
        # maybe some other privilege names


    # IRequestHandler methods
    # def match_request(self, req):
    #     match = re.match(r'/api/ticket/([0-9]+)$', path_info)
    #     if match:
    #         req.args['id'] = match.group(1)
    #         return True


    def match_request(self, req):
        match = TICKET_RE.match(req.path_info)
        if match:
            print "PORC"
            req.args['productid'] = m.group('pid')
            req.args['ticketid'] = m.group('tid')
            return not match is None



    def process_request(self, req):
        ticketid = req.args.get('id')
        ticket = Ticket(self.env, ticketid)
        data = {'ticket': Ticket(self.env, ticketid)}
        return 'bh_emb_ticket.html', data, None


    ### ITemplateProvider methods

    def get_templates_dirs(self):
        resource_filename = pkg_resources.resource_filename
        return [resource_filename('bhembedding', 'templates')]

    def get_htdocs_dirs(self):
        return [] # temporarily, since there are no html docs yet
        # from pkg_resources import resource_filename
        # return [('ticket', resource_filename('bhembedding', 'htdocs'))]


 # # Ticket system
 #    Table('ticket', key='id')[
 #        Column('id', auto_increment=True),
 #        Column('type'),
 #        Column('time', type='int64'),
 #        Column('changetime', type='int64'),
 #        Column('component'),
 #        Column('severity'),
 #        Column('priority'),
 #        Column('owner'),
 #        Column('reporter'),
 #        Column('cc'),
 #        Column('version'),
 #        Column('milestone'),
 #        Column('status'),
 #        Column('resolution'),
 #        Column('summary'),
 #        Column('description'),
 #        Column('keywords'),
 #        Index(['time']),
 #        Index(['status'])],
