"""setup for live syntax highlighting"""
from setuptools import setup, find_packages

setup(
    name = 'BloodhoundLiveSyntaxHighlight',
    version = '0.1',
    description = "Live Syntax Highlighting support in wiki editors for \
    Apache(TM) Bloodhound.",
    author = "Apache Bloodhound",
    license = "Apache License v2",
    url = "http://bloodhound.apache.org/",
    packages = ['bhlivesyntaxhighlight'],
    package_data = {'bhlivesyntaxhighlight' : ['htdocs/js/*.js',
    'htdocs/css/*.css','templates/*.html']},
    entry_points = {'trac.plugins': [
            'bhlivesyntaxhighlight = \
            bhlivesyntaxhighlight.bhlivesyntaxhighlight',
        ],},
)