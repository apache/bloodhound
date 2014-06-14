from trac.ticket.model import Ticket
from bhsearch.search_resources.ticket_search import TicketIndexer
from trac.core import Component, implements, TracError
from bhsearch.search_resources.base import BaseIndexer

class TicketSearchModel(BaseIndexer):

  def _fetch_tickets(self,  **kwargs):
    for ticket_id in self._fetch_ids(**kwargs):
      yield Ticket(self.env, ticket_id)

  def _fetch_ids(self, **kwargs):
    sql = "SELECT id FROM ticket"
    args = []
    conditions = []
    for key, value in kwargs.iteritems():
      args.append(value)
      conditions.append(key + "=%s")
    if conditions:
      sql = sql + " WHERE " + " AND ".join(conditions)
    for row in self.env.db_query(sql, args):
      yield int(row[0])

  def get_entries_for_index(self):
    for ticket in self._fetch_tickets():
      yield TicketIndexer(self.env).build_doc(ticket)

