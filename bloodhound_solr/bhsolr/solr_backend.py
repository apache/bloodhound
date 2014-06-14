import pkg_resources

from solr import Solr
from trac.ticket.model import Ticket
from trac.core import Component, implements, TracError
from trac.ticket.api import TicketSystem
from bhsearch.search_resources.ticket_search import TicketIndexer
from datetime import datetime
from trac.util.datefmt import utc

UNIQUE_ID = "unique_id"

class SolrModel(Component):
  implements(ISearchBackend)

  def __init__(self):
    resource_filename = pkg_resources.resource_filename
    path = resource_filename(__name__, "schemadoc")
    # self.solr_interface = Solr("http://localhost:8983/solr/", path + '/schema.xml').solr_interface
    self.solr_interface = Solr("http://localhost:8983/solr/").solr_interface


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


  def optimize():
    self.solr_interface.optimize()


  def query(self, query):
    self.solr_instance.solr_interface.query(query).execute()


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

if __name__ == '__main__':
  env = trac.env.Environment("/Users/antonia/Documents/Code/bloodhound/installer/bloodhound/environments/main")
  db_connection = env.get_db_cnx()
  cursor = db_connection.cursor()
  a = cursor.execute("select * from ticket")
  ticket = a.fetchall()[0]

  # for result in si.query(name="Ticket").execute():
    # print result
