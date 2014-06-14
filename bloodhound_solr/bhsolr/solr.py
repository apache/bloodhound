from sunburnt import SolrInterface
from httplib2 import Http

class Solr():

  def __init__(self, solr_url):
    """ Creates a SolrInterface object with the solr server url and a custom schema
      file"""
    self.solr_url = solr_url
    self.solr_interface = SolrInterface(url=solr_url)
