import re
import os
import pkg_resources

from trac.web.main import IRequestHandler
from trac.core import Component, TracError, implements
from trac.ticket.model import Ticket
from trac.web.chrome import ITemplateProvider
from bhsolr.search_resources.ticket_search import TicketSearchModel
from bhsolr.search_resources.milestone_search import MilestoneSearchModel
from bhsolr.search_resources.changeset_search import ChangesetSearchModel
from bhsolr.search_resources.wiki_search import WikiSearchModel
from bhsolr.solr_backend import SolrModel

class BloodhoundSolrSearchModule(Component):
    implements(IRequestHandler, ITemplateProvider)

    def match_request(self, req):
      if re.match(r'/solr$', req.path_info):
        return True

    def process_request(self, req):
      # changeset_doc = next(ChangesetSearchModel(self.env).get_entries_for_index())
      milestone_doc = next(MilestoneSearchModel(self.env).get_entries_for_index())
      ticket_doc = next(TicketSearchModel(self.env).get_entries_for_index())
      wiki_doc = next(WikiSearchModel(self.env).get_entries_for_index())

      SolrModel(self.env).addDoc(ticket_doc)
      SolrModel(self.env).addDoc(milestone_doc)
      SolrModel(self.env).addDoc(wiki_doc)

      data = {}
      return 'bh_solr_test.html', data, None

    def get_templates_dirs(self):
        resource_filename = pkg_resources.resource_filename
        return [resource_filename('bhsolr', 'templates')]

    def get_htdocs_dirs(self):
        resource_filename = pkg_resources.resource_filename
        return [('solr', resource_filename('bhsolr', 'htdocs'))]

