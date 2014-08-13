import unittest

from trac.test import EnvironmentStub, Mock, MockPerm
from trac.util.datefmt import utc
from trac.web.chrome import Chrome
from bhsearch.tests.base import BaseBloodhoundSearchTest

class SolrBackendTestCase(BaseBloodhoundSearchTest):
  def setUp(self):
    super(SolrBackendTestCase, self).setUp()
    self.solr_backend = SolrBackend(self.env)
    # self.parser = DefaultQueryParser(self.env)

def suite():
  suite = unittest.TestSuite()
  suite.addTest(unittest.makeSuite(SolrBackendTestCase))
  return suite


if __name__ == '__main__':
  unittest.main(defaultTest='suite')
