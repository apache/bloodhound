"""setup for embeddable objects plugin"""
from setuptools import setup

setup(
    name = 'BloodhoundEmbeddingPlugin',
    version = '0.1',
    description = "Embeddable objects plugin support for Apache(TM) Bloodhound.",
    author = "Apache Bloodhound",
    license = "Apache License v2",
    url = "http://bloodhound.apache.org/",
    packages = ['bhembedding', 'bhembedding.tests',],
    package_data = {'bhembedding' : ['templates/*.html', 'htdocs/*.css',]},
    entry_points = {'trac.plugins': [
            'bhembedding.api = bhembedding.api',
        ],},
    test_suite='bhembedding.tests.test_suite',
)


