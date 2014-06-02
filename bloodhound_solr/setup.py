"""setup for embeddable objects plugin"""
from setuptools import setup

setup(
    name = 'BloodhoundSolrPlugin',
    version = '0.1',
    description = "Apache Solr support for Apache(TM) Bloodhound.",
    author = "Apache Bloodhound",
    license = "Apache License v2",
    url = "http://bloodhound.apache.org/",
    packages = ['bhsolr',],
    package_data = {'bhsolr' : []},
    entry_points = {'trac.plugins': ['bhsolr.index = bhsolr.index'],},
    test_suite='bhsorl.tests.test_suite',
)


