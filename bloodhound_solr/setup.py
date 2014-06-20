from setuptools import setup, find_packages

PKG_INFO = {'bhsolr': ['schemadoc/*.xml'],
            'bhsolr.search_resources' : [],
            }



ENTRY_POINTS = {
          'trac.plugins': [
          'bhsolr.api = bhsolr.api',
          'bhsolr.solr = bhsolr.solr',
          'bhsolr.admin = bhsolr.admin',
          'bhsolr.solr_backend = bhsolr.solr_backend',
          'bhsolr.search_resources.ticket_search = bhsolr.search_resources.ticket_search',
          'bhsolr.search_resources.milestone_search = bhsolr.search_resources.milestone_search',
          'bhsolr.search_resources.changeset_search = bhsolr.search_resources.changeset_search',
          'bhsolr.search_resources.wiki_search = bhsolr.search_resources.wiki_search'
      ],}

setup(
  name = 'BloodhoundSolrPlugin',
  version = '0.1',
  description = "Apache Solr support for Apache(TM) Bloodhound.",
  author = "Apache Bloodhound",
  license = "Apache License v2",
  url = "http://bloodhound.apache.org/",
  # package_dir = PKG_INFO,
  packages = find_packages(),
  package_data = PKG_INFO,
  include_package_data=True,
  entry_points = ENTRY_POINTS,
  test_suite='bhsolr.tests.test_suite',
)
