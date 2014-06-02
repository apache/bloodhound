import sunburnt
from solr import Solr

class SolrIndex(object):
  def __init__(self, solr_instance):
    self.solr_instance = solr_instance

  def index(self, doc):
    self.solr_instance.solr_interface.add(doc)
    self.solr_instance.solr_interface.commit()

  def query(self, query):
    self.solr_instance.solr_interface.query(query)

if __name__ == '__main__':

  document = {"id":"0553573403",
              "name": "Ticket 1"}

  si = Solr("http://localhost:8983/solr/")
  sindex = SolrIndex(si)
  sindex.index(document)
  sindex.query("Ticket")

