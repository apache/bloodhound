from bhsolr.search_resources import TicketSearchModel
from trac.core import Component, implements

class BloodhoundSolrApi(Component):
  def populate_index(self):
    tickets = TicketSearchModel(self.env).get_entries_for_index()
    print tickets
