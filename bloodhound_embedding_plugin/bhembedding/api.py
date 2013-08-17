import re
import pkg_resources
from datetime import datetime, date, time

from trac.core import *
from trac.web.chrome import ITemplateProvider
from trac.web.main import IRequestHandler
from trac.perm import IPermissionRequestor, PermissionCache, PermissionSystem
from trac.util import escape, Markup
from trac.core import Component, TracError, implements
from trac.ticket import model
from trac.core import TracError
from trac.ticket.model import Ticket, Milestone, MilestoneCache, Version, Component as component
from trac.ticket.web_ui import TicketModule
from trac.ticket.api import TicketSystem
from trac.ticket.query import Query, QueryModule, TicketQueryMacro, QueryValueError, QuerySyntaxError
from multiproduct.model import Product
from multiproduct.web_ui import ProductModule
from multiproduct.ticket import query
from trac.resource import Resource, ResourceNotFound
from trac.ticket.roadmap import get_tickets_for_milestone
from trac.attachment import Attachment

from trac.web.href import Href

from multiproduct.env import ProductEnvironment

from multiproduct.ticket.web_ui import ProductTicketModule

class EmbeddingSystem(Component):
    implements(IRequestHandler, IPermissionRequestor, ITemplateProvider)

    # IPermissionRequestor method
    def get_permission_actions(self):
        return ['TICKET_EMBED', 'MILESTONE_EMBED', 'PRODUCT_EMBED', 'QUERY_EMBED']

    def get_tickets_for_product(self, env, product=''):
        """Retrieve all tickets associated with the product."""
        q = query.ProductQuery.from_string(env, 'product=%s' % product)
        return q.execute()


    def changeLog(self, id):
        t = Ticket(self.env, id)
        for date, author, field, old, new, permanent in t.get_changelog():
            yield (date, author, field, old, new, permanent)


    def query(self, req, qstr):
        q = Query.from_string(self.env, qstr)
        filters = Query.to_string(q)
        ticket_realm = Resource('ticket')
        out = []
        for t in q.execute(req):
            tid = t['id']
            if 'TICKET_VIEW' in req.perm(ticket_realm(id=tid)):
                out.append(tid)
        return filters, out


    def get_attachments(self, realm, id):
        return [a.filename for a in Attachment.select(self.env, realm, id)]


    # IRequestHandler methods

    def match_request(self, req):
        if re.match(r'/embed/ticket/([0-9]+)$', req.path_info):
            match = re.match(r'/embed/(ticket)/([0-9]+)$', req.path_info)
            req.args['name'] = match.group(1)
            req.args['id'] = match.group(2)
            return True
        elif re.match(r'/embed/milestone/(.+)$', req.path_info):
            match = re.match(r'/embed/(milestone)/(.+)$', req.path_info)
            req.args['name'] = match.group(1)
            req.args['id'] = match.group(2)
            return True
        elif re.match(r'/embed/products/(.+)$', req.path_info):
            match = re.match(r'/embed/(products)/(.+)$', req.path_info)
            req.args['name'] = match.group(1)
            req.args['id'] = match.group(2)
            return True
        elif req.path_info == '/embed/query':
            req.args['name'] = 'query'
            return True


    def process_request(self, req):
        name = req.args.get('name')
        if not (name == 'query'):
            id = req.args.get('id')

        if name == 'ticket':
            comm_num = 0
            attachment_num = len(self.get_attachments('ticket', id))
            ticket_log = self.changeLog(id)
            for log in ticket_log:
                if log[2] == 'comment' and log[4]:
                    comm_num += 1

            ticket = Ticket(self.env, id)
            data = {'ticket': ticket,
                    'comm_num': comm_num,
                    'attachment_num': attachment_num}
            return 'bh_emb_ticket.html', data, None

        elif name == 'milestone':
            ticket_num = len(get_tickets_for_milestone(self.env, milestone=id))
            attachment_num = len(self.get_attachments('milestone', id))
            data = {'milestone': Milestone(self.env, id),
                    'product': self.env.product,
                    'ticket_number': ticket_num,
                    'attachment_number': attachment_num }
            return 'bh_emb_milestone.html', data, None

        elif name == 'products':
            product = Product(self.env, {'prefix': id})
            ticket_num = len(self.get_tickets_for_product(self.env, id))
            product_env = ProductEnvironment(self.env, product.prefix)
            milestone_num = len(Milestone.select(product_env))
            version_num = len(Version.select(product_env))
            components = component.select(product_env)
            component_num = 0
            for c in components:
                component_num += 1

            data = {'product': product,
                    'ticket_num': ticket_num,
                    'owner': product.owner,
                    'milestone_num': milestone_num,
                    'version_num': version_num,
                    'component_num': component_num}
            return 'bh_emb_product.html', data, None
        elif name == 'query':
            qstr = req.query_string

            if qstr=='':
                # if req.authname and req.authname != 'anonymous':
                #     qstr = 'status!=closed&owner=' + req.authname
                # else:
                qstr = 'status!=closed'

            qresults = self.query(req, qstr)
            filters = qresults[0]
            tickets = qresults[1]

            data={'tickets': tickets,
                  'query': qstr,
                  'filters': filters}
            return 'bh_emb_query.html', data, None
        else:
            msg = "It is not possible to embed this resource."
            raise ResourceNotFound((msg), ("Invalid resource"))



    ### ITemplateProvider methods

    def get_templates_dirs(self):
        resource_filename = pkg_resources.resource_filename
        return [resource_filename('bhembedding', 'templates')]

    def get_htdocs_dirs(self):
        resource_filename = pkg_resources.resource_filename
        return [('embedding', resource_filename('bhembedding', 'htdocs'))]
