import pkg_resources

from solr import Solr
from trac.ticket.model import Ticket
from trac.core import Component, implements, TracError
from trac.ticket.api import TicketSystem
from bhsearch.search_resources.ticket_search import TicketIndexer
from datetime import datetime
from trac.util.datefmt import utc
from bhsearch.api import ISearchBackend
from bhsearch.query_parser import DefaultQueryParser

UNIQUE_ID = "unique_id"

class SolrBackend(Component):
  implements(ISearchBackend)

  def __init__(self):
    resource_filename = pkg_resources.resource_filename
    path = resource_filename(__name__, "schemadoc")
    self.solr_interface = Solr("http://localhost:8983/solr/").solr_interface # TODO: Refactor
    self.field_boosts = DefaultQueryParser(self.env).field_boosts


  def add_doc(self, doc, operation_context=None):
    self._reformat_doc(doc)
    doc[UNIQUE_ID] = self._create_unique_id(doc.get("product", ''),
                                            doc["type"],
                                            doc["id"])
    self.solr_interface.add(doc)
    self.solr_interface.commit()


  def delete_doc(product, doc_type, doc_id, operation_context=None):
    unique_id = self._create_unique_id(product, doc_type, doc_id)
    self.solr_interface.delete(unique_id)


  def optimize(self):
    self.solr_interface.optimize()

  def query(self, query, query_string, sort = None, fields = None, filter = None,
            facets = None, pagenum = 1, pagelen = 20, highlight = False,
            highlight_fields = None, context = None):

    tokens = set([token.text for token in query.all_tokens()])
    final_query_chain = None
    for token in tokens:
      token_query_chain = self._search_fields_for_token(token)
      if final_query_chain == None:
        final_query_chain = token_query_chain
      else:
        final_query_chain |= token_query_chain

    print final_query_chain
    return None

  def is_index_outdated(self):
    return False

  def recreate_index(self):
    return True

  def start_operation(self):
    return None

  def _search_fields_for_token(self, token):
    query_chain = None
    for field, boost in self.field_boosts.iteritems():
      field_token_dict = {field: token}
      if query_chain == None:
        query_chain = self.solr_interface.Q(**field_token_dict)**boost
      else:
        query_chain |= self.solr_interface.Q(**field_token_dict)**boost

    return query_chain

  def _reformat_doc(self, doc):
    for key, value in doc.items():
      if key is None:
        del doc[None]
      elif value is None:
        del doc[key]
      elif isinstance(value, basestring) and value == "":
        del doc[key]
      else:
        doc[key] = self._to_solr_format(value)


  def _to_solr_format(self, value):
    if isinstance(value, basestring):
      value = unicode(value)
    elif isinstance(value, datetime):
      value = self._convert_date_to_tz_naive_utc(value)
    return value


  def _convert_date_to_tz_naive_utc(self, value):
    if value.tzinfo:
      utc_time = value.astimezone(utc)
      value = utc_time.replace(tzinfo=None)
    return value


  def _create_unique_id(self, product, doc_type, doc_id):
    if product:
      return u"%s:%s:%s" % (product, doc_type, doc_id)
    else:
      return u"%s:%s" % (doc_type, doc_id)

  def getInstance(self):
    return self.solr_interface


