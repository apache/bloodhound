# -*- coding: utf-8 -*-
#
#  Licensed to the Apache Software Foundation (ASF) under one
#  or more contributor license agreements.  See the NOTICE file
#  distributed with this work for additional information
#  regarding copyright ownership.  The ASF licenses this file
#  to you under the Apache License, Version 2.0 (the
#  "License"); you may not use this file except in compliance
#  with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing,
#  software distributed under the License is distributed on an
#  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#  KIND, either express or implied.  See the License for the
#  specific language governing permissions and limitations
#  under the License.

"""Tests for Apache(TM) Bloodhound's core wiki syntax in product environments"""

import os.path
import pkg_resources
import re
import shutil
import tempfile
import unittest

from genshi.core import escape

from trac.attachment import Attachment
from trac.web.href import Href
from trac.tests import wikisyntax
from trac.ticket.model import Ticket
from trac.ticket.tests import wikisyntax as ticket_wikisyntax
from trac.util.text import to_unicode

from multiproduct.api import PRODUCT_SYNTAX_DELIMITER
from multiproduct.env import ProductEnvironment
from multiproduct.ticket.query import ProductTicketQueryMacro
from tests.env import MultiproductTestCase
from tests.wiki import formatter

def attachment_setup(tc):
    import trac.ticket.api
    import trac.wiki.api
    tc.global_env.path = os.path.join(tempfile.gettempdir(), 'trac-tempenv')
    if tc.env is not tc.global_env:
        del tc.env.path
    attachment = Attachment(tc.env, 'wiki', 'WikiStart')
    attachment.insert('file.txt', tempfile.TemporaryFile(), 0)
    attachment = Attachment(tc.env, 'ticket', 123)
    attachment.insert('file.txt', tempfile.TemporaryFile(), 0)
    attachment = Attachment(tc.env, 'wiki', 'SomePage/SubPage')
    attachment.insert('foo.txt', tempfile.TemporaryFile(), 0)

def attachment_teardown(tc):
    tc.global_env.reset_db()
    shutil.rmtree(tc.global_env.path)

def ticket_setup(tc):
    ticket = Ticket(tc.env)
    ticket.values.update({'reporter': 'santa',
                          'summary': 'This is the summary',
                          'status': 'new'})

    # FIXME : UGLY ! Should not be explicit for product environments
    ticket['product'] = (tc.env.product.prefix
                         if isinstance(tc.env, ProductEnvironment)
                         else '')

    ticket.insert()


# Full syntax
PRODUCT_LINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-link-tests.txt'))
PRODUCT_ATTACHMENT_LINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-attachment-link-tests.txt')) 
PRODUCT_SEARCH_LINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-search-link-tests.txt'))
PRODUCT_TICKET_LINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-ticket-link-tests.txt'))
PRODUCT_TICKET_JIRA = to_unicode(pkg_resources.resource_string(
        __name__, 'product-ticket-jira-tests.txt'))
PRODUCT_REPORT_LINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-report-link-tests.txt'))
PRODUCT_MILESTONE_LINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-milestone-link-tests.txt'))
PRODUCT_QUERY_LINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-query-link-tests.txt'))
PRODUCT_QUERY2_LINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-query2-link-tests.txt'))
PRODUCT_COMMENT_LINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-comment-link-tests.txt'))

# Compact syntax
PRODUCT_ATTACHMENT_SHORTLINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-attachment-link-tests.short.txt')) 
PRODUCT_SEARCH_SHORTLINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-search-link-tests.short.txt'))
PRODUCT_TICKET_SHORTLINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-ticket-link-tests.short.txt'))
PRODUCT_REPORT_SHORTLINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-report-link-tests.short.txt'))
PRODUCT_MILESTONE_SHORTLINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-milestone-link-tests.short.txt'))
PRODUCT_QUERY_SHORTLINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-query-link-tests.short.txt'))
PRODUCT_COMMENT_SHORTLINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-comment-link-tests.short.txt'))

PRODUCT_NOMATCH_LINKS = to_unicode(pkg_resources.resource_string(
        __name__, 'product-nomatch-link-tests.txt'))

PRODUCT_PREFIXES = MultiproductTestCase.PRODUCT_DATA.keys()
PRODUCT_PREFIXES.remove(MultiproductTestCase.default_product)

def clear_base_href_setup(tc):
    tc.global_env.href = Href('/') 
    tc.global_env.abs_href = Href('http://www.example.com/')
    if tc.env is not tc.global_env:
        del tc.env.abs_href
        del tc.env.href
    tc.env._href = tc.env._abs_href = None

def load_products_setup(prefixes):
    def _load_products_setup(tc):
        clear_base_href_setup(tc)

        for p in prefixes :
            tc._load_product_from_data(tc.global_env, p)
    return _load_products_setup

def link_mp_setup(_setup):
    def _link_mp_setup(tc):
        clear_base_href_setup(tc)
        _setup(tc)

    return _link_mp_setup


# Product testing contexts explained
#
# Product testing contexts are a hack used to hijack the mechanism
# used by Trac test suite in order to run wiki test cases in product context  
#
# title_prefix          : prepend this text to test case summary
# link_prefix           : used to put link references in given product context
# link_title_prefix     : short text to highlight environment context
# path_prefix           : prepended to URLs expanded using `link_prefix`
# main_product          : prefix identifying the product bound to test case
#                         `env` attribute
# setup_product         : optional prefix of the product that will be setup  
#                         i.e. the product under test
# load_products         : optional product prefixes list to load at setup time
# *_product_name        : target product name (e.g. setup_product_name ) 
# *_escaped             : escaped forms used to match output
TEST_PRODUCT_CONTEXTS = [
                         {'tc_title_prefix' : 'product: links',
                          'link_prefix' : 'product:tp1:',
                          'link_prefix_quote' : 'product:"tp1:',
                          'path_prefix' : '/products/tp1',
                          'main_product' : 'tp2',
                          'setup_product' : 'tp1',
                          'link_title_prefix' : '[tp1] ',
                          },
                         {'tc_title_prefix' : 'product: links unicode prefix',
                          'link_prefix' : u'product:xü:',
                          'link_prefix_quote' : u'product:"xü:',
                          'path_prefix' : '/products/x%C3%BC',
                          'main_product' : 'tp2',
                          'setup_product' : u'xü',
                          'link_title_prefix' : u'[xü] ',
                          },

                         # Ignored as TracLinks resolver won't match expression
                         #{'tc_title_prefix' : 'product:: refs to global',
                         # 'link_prefix' : 'product::',
                         # 'path_prefix' : '',
                         # 'main_product' : 'tp2',
                         # 'setup_product' : None,
                         # 'link_title_prefix' : '<global> '
                         # },

                         {'tc_title_prefix' : 'global: links',
                          'link_prefix' : 'global:',
                          'link_prefix_quote' : 'global:"',
                          'path_prefix' : '',
                          'main_product' : 'tp2',
                          'setup_product' : '',
                          'link_title_prefix' : '&lt;global&gt; ',
                          },
                        ]

TEST_PRODUCT_CONTEXTS_COMPACT = [
                          {'tc_title_prefix' : 'short product syntax',
                          'link_prefix' : 'tp1' + PRODUCT_SYNTAX_DELIMITER,
                          'link_prefix_quote' : 'tp1%s"' % PRODUCT_SYNTAX_DELIMITER,
                          'path_prefix' : '/products/tp1',
                          'main_product' : 'tp2',
                          'setup_product' : 'tp1',
                          'link_title_prefix' : '[tp1] ',
                          },
                         {'tc_title_prefix' : 'short product syntax unicode prefix',
                          'link_prefix' : u'xü' + PRODUCT_SYNTAX_DELIMITER,
                          'link_prefix_quote' : u'xü%s"' % PRODUCT_SYNTAX_DELIMITER,
                          'path_prefix' : '/products/x%C3%BC',
                          'main_product' : 'tp2',
                          'setup_product' : u'xü',
                          'link_title_prefix' : u'[xü] ',
                          },
                        ]

for ctxlst in (TEST_PRODUCT_CONTEXTS, TEST_PRODUCT_CONTEXTS_COMPACT):
    for _ctx in ctxlst:
        _product_extras = {}
        for k,v in _ctx.iteritems():
            _product_extras[k + '_escaped'] = escape(v)
            if k.endswith('_product'):
                if v in MultiproductTestCase.PRODUCT_DATA:
                    _product_extras[k + '_name'] = MultiproductTestCase.PRODUCT_DATA[v]['name']
                else:
                    _product_extras[k + '_name'] = ''
                _product_extras[k + '_name_escaped'] = escape(_product_extras[k + '_name'])
        _ctx.update(_product_extras)

del _ctx, k, v, _product_extras

def test_suite():
    suite = unittest.TestSuite()

    # Legacy test cases
    suite.addTest(formatter.test_suite(wikisyntax.SEARCH_TEST_CASES, 
                                  file=wikisyntax.__file__))
    suite.addTest(formatter.test_suite(wikisyntax.ATTACHMENT_TEST_CASES, 
                                  file=wikisyntax.__file__,
                                  context=('wiki', 'WikiStart'),
                                  setup=attachment_setup,
                                  teardown=attachment_teardown))
    suite.addTest(formatter.test_suite(wikisyntax.EMAIL_TEST_CASE_DEFAULT, 
                                  file=wikisyntax.__file__,
                                  context=wikisyntax.email_default_context()))
    suite.addTest(formatter.test_suite(wikisyntax.EMAIL_TEST_CASE_NEVER_OBFUSCATE,
                                  file=wikisyntax.__file__,
                                  context=wikisyntax.email_default_context(),
                                  setup=wikisyntax.email_never_obfuscate_setup))

    # Product wiki syntax
    suite.addTest(formatter.test_suite(PRODUCT_LINKS, 
                                  setup=load_products_setup(PRODUCT_PREFIXES),
                                  file=__file__))
    suite.addTests(formatter.test_suite(PRODUCT_SEARCH_LINKS % ctx, 
                                  file=__file__,
                                  setup=clear_base_href_setup,
                                  mpctx=ctx)
                   for ctx in TEST_PRODUCT_CONTEXTS)
    suite.addTests(formatter.test_suite(PRODUCT_ATTACHMENT_LINKS % ctx, 
                                  file=__file__,
                                  context=('wiki', 'WikiStart'),
                                  setup=link_mp_setup(attachment_setup),
                                  teardown=attachment_teardown,
                                  mpctx=ctx)
                   for ctx in TEST_PRODUCT_CONTEXTS)
    suite.addTests(formatter.test_suite(PRODUCT_TICKET_LINKS % ctx, 
                                  link_mp_setup(ticket_wikisyntax.ticket_setup), 
                                  __file__,
                                  # No need to invoke it anymore
                                  # ticket_wikisyntax.ticket_teardown,
                                  mpctx=ctx)
                   for ctx in TEST_PRODUCT_CONTEXTS)
    suite.addTests(formatter.test_suite(PRODUCT_TICKET_JIRA % ctx, 
                                  link_mp_setup(ticket_wikisyntax.ticket_setup), 
                                  __file__,
                                  # No need to invoke it anymore
                                  # ticket_wikisyntax.ticket_teardown,
                                  mpctx=ctx)
                   for ctx in TEST_PRODUCT_CONTEXTS 
                   if ctx['path_prefix'])
    suite.addTests(formatter.test_suite(PRODUCT_REPORT_LINKS % ctx, 
                                  link_mp_setup(ticket_wikisyntax.report_setup), 
                                  __file__,
                                  mpctx=ctx)
                   for ctx in TEST_PRODUCT_CONTEXTS)
    suite.addTests(formatter.test_suite(PRODUCT_MILESTONE_LINKS % ctx, 
                                  link_mp_setup(ticket_wikisyntax.milestone_setup),
                                  __file__, 
                                  ticket_wikisyntax.milestone_teardown,
                                  mpctx=ctx)
                   for ctx in TEST_PRODUCT_CONTEXTS)
    suite.addTests(formatter.test_suite(PRODUCT_QUERY_LINKS % ctx, 
                                  link_mp_setup(ticket_setup), 
                                  __file__,
                                  ticket_wikisyntax.ticket_teardown,
                                  mpctx=ctx)
                   for ctx in TEST_PRODUCT_CONTEXTS)
    suite.addTests(formatter.test_suite(PRODUCT_QUERY2_LINKS % ctx, 
                                  link_mp_setup(ticket_wikisyntax.query2_setup), 
                                  __file__,
                                  ticket_wikisyntax.query2_teardown,
                                  mpctx=ctx)
                   for ctx in TEST_PRODUCT_CONTEXTS)
    suite.addTests(formatter.test_suite(PRODUCT_COMMENT_LINKS % ctx,
                                  clear_base_href_setup,
                                  __file__,
                                  mpctx=ctx)
                   for ctx in TEST_PRODUCT_CONTEXTS)


    # Compact syntax
    suite.addTests(formatter.test_suite(PRODUCT_SEARCH_SHORTLINKS % ctx, 
                                  file=__file__,
                                  setup=clear_base_href_setup,
                                  mpctx=ctx)
                   for ctx in TEST_PRODUCT_CONTEXTS_COMPACT)
    suite.addTests(formatter.test_suite(PRODUCT_ATTACHMENT_SHORTLINKS % ctx, 
                                  file=__file__,
                                  context=('wiki', 'WikiStart'),
                                  setup=link_mp_setup(attachment_setup),
                                  teardown=attachment_teardown,
                                  mpctx=ctx)
                   for ctx in TEST_PRODUCT_CONTEXTS_COMPACT)
    suite.addTests(formatter.test_suite(PRODUCT_TICKET_SHORTLINKS % ctx, 
                                  link_mp_setup(ticket_wikisyntax.ticket_setup), 
                                  __file__,
                                  # No need to invoke it anymore
                                  # ticket_wikisyntax.ticket_teardown,
                                  mpctx=ctx)
                   for ctx in TEST_PRODUCT_CONTEXTS_COMPACT)

    suite.addTests(formatter.test_suite(PRODUCT_REPORT_SHORTLINKS % ctx, 
                                  link_mp_setup(ticket_wikisyntax.report_setup), 
                                  __file__,
                                  mpctx=ctx)
                   for ctx in TEST_PRODUCT_CONTEXTS_COMPACT)
    suite.addTests(formatter.test_suite(PRODUCT_MILESTONE_SHORTLINKS % ctx, 
                                  link_mp_setup(ticket_wikisyntax.milestone_setup),
                                  __file__, 
                                  ticket_wikisyntax.milestone_teardown,
                                  mpctx=ctx)
                   for ctx in TEST_PRODUCT_CONTEXTS_COMPACT)
    suite.addTests(formatter.test_suite(PRODUCT_QUERY_SHORTLINKS % ctx, 
                                  link_mp_setup(ticket_setup), 
                                  __file__,
                                  ticket_wikisyntax.ticket_teardown,
                                  mpctx=ctx)
                   for ctx in TEST_PRODUCT_CONTEXTS_COMPACT)
    suite.addTests(formatter.test_suite(PRODUCT_COMMENT_SHORTLINKS % ctx,
                                  clear_base_href_setup,
                                  __file__,
                                  mpctx=ctx)
                   for ctx in TEST_PRODUCT_CONTEXTS_COMPACT)


    # Unmatched expressions
    suite.addTest(formatter.test_suite(PRODUCT_NOMATCH_LINKS,
                                  file=__file__))

    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

