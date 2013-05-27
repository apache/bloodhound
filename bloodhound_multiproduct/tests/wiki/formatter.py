
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

"""Tests for Apache(TM) Bloodhound's wiki formatters in product environments"""

import os.path
import re
import unittest

from trac.test import Mock, MockPerm, locale_en
from trac.util.datefmt import utc
from trac.web.href import Href
from trac.web.main import FakeSession
from trac.wiki.tests import formatter

from multiproduct.env import ProductEnvironment
from multiproduct.model import Product
from tests.env import MultiproductTestCase


class ProductWikiTestCase(formatter.WikiTestCase, MultiproductTestCase):
    maxDiff = None

    def setUp(self):
        self._prepare_env()

        self._setup_test_log(self.global_env)
        formatter.WikiTestCase.setUp(self)
        if self.context.req:
            self.context.req.session = FakeSession()
        if self.mpctx:
            candidates = set(self.mpctx.get('load_products', []) + 
                             [self.mpctx.get('main_product')])
            candidates -= set([self.default_product, None, 
                              self.mpctx.get('setup_product')])
            for prefix in candidates:
                self._load_product_from_data(self.env, prefix)

            prefix = self.mpctx.get('main_product', NotImplemented)
            if prefix is None:
                self.env = self.global_env
            elif prefix is not NotImplemented \
                    and (self.env is self.global_env or 
                         prefix != self.env.product.prefix):
                self.env = ProductEnvironment(self.global_env, prefix)
            # Enable multi-product components
            self.env.config.set('components', 'multiproduct.*', 'enabled')

    def _prepare_env(self):
        all_test_components = [
                    formatter.HelloWorldMacro, formatter.DivHelloWorldMacro,
                    formatter.TableHelloWorldMacro, formatter.DivCodeMacro,
                    formatter.DivCodeElementMacro, formatter.DivCodeStreamMacro,
                    formatter.NoneMacro, formatter.WikiProcessorSampleMacro,
                    formatter.SampleResolver]
        self.global_env = self._setup_test_env(
            enable=['trac.*', 'multiproduct.*'] + all_test_components
        )

        self._upgrade_mp(self.global_env)
        self._load_product_from_data(self.global_env, self.default_product)
        prefix = self.default_product
        if self.mpctx:
            prefix = self.mpctx.get('setup_product', prefix)
            if prefix and prefix != self.default_product:
                self._load_product_from_data(self.global_env, prefix)
        if prefix:
            self.env = ProductEnvironment(self.global_env,
                                          prefix or self.default_product)
        else:
            self.env = self.global_env

        self.env.path = ''
        config = self.env.config
        # -- intertrac support
        config.set('intertrac', 'trac.title', "Trac's Trac")
        config.set('intertrac', 'trac.url',
                   "http://trac.edgewall.org")
        config.set('intertrac', 't', 'trac')
        config.set('intertrac', 'th.title', "Trac Hacks")
        config.set('intertrac', 'th.url',
                   "http://trac-hacks.org")
        config.set('intertrac', 'th.compat', 'false')
        # -- safe schemes
        config.set('wiki', 'safe_schemes',
                   'file,ftp,http,https,svn,svn+ssh,'
                   'rfc-2396.compatible,rfc-2396+under_score')

        req = Mock(href=Href('/'), abs_href=Href('http://www.example.com/'),
                   authname='anonymous', perm=MockPerm(), tz=utc, args={},
                   locale=locale_en, lc_time=locale_en)

        self.env.href = req.href
        self.env.abs_href = req.abs_href

    def tearDown(self):
        self.global_env.reset_db()
        try:
            if self._teardown:
                self._teardown(self)
        finally:
            self.global_env = self._env = None

    def __init__(self, title, input, correct, file, line, setup=None,
                 teardown=None, context=None, mpctx=None):
        MultiproductTestCase.__init__(self, 'test')
        self.mpctx = mpctx
        formatter.WikiTestCase.__init__(self, title, input, correct, file, line, 
                setup, teardown, context)

class ProductOneLinerTestCase(ProductWikiTestCase):
    formatter = formatter.OneLinerTestCase.formatter.im_func

class ProductEscapeNewLinesTestCase(ProductWikiTestCase):
    generate_opts = formatter.EscapeNewLinesTestCase.generate_opts 
    formatter = formatter.EscapeNewLinesTestCase.formatter.im_func

class ProductOutlineTestCase(ProductWikiTestCase):
    formatter = formatter.OutlineTestCase.formatter.im_func


def test_suite(data=None, setup=None, file=formatter.__file__, 
        teardown=None, context=None, mpctx=None):
    suite = unittest.TestSuite()
    def add_test_cases(data, filename):
        tests = re.compile('^(%s.*)$' % ('=' * 30), re.MULTILINE).split(data)
        next_line = 1
        line = 0
        for title, test in zip(tests[1::2], tests[2::2]):
            title = title.lstrip('=').strip()
            if line != next_line:
                line = next_line
            if not test or test == '\n':
                continue
            next_line += len(test.split('\n')) - 1
            if 'SKIP' in title or 'WONTFIX' in title:
                continue
            blocks = test.split('-' * 30 + '\n')
            if len(blocks) < 5:
                blocks.extend([None,] * (5 - len(blocks)))
            input, page, oneliner, page_escape_nl, outline = blocks[:5]
            if page:
                page = ProductWikiTestCase(
                    title, input, page, filename, line, setup,
                    teardown, context, mpctx)
            if oneliner:
                oneliner = ProductOneLinerTestCase(
                    title, input, oneliner[:-1], filename, line, setup,
                    teardown, context, mpctx)
            if page_escape_nl:
                page_escape_nl = ProductEscapeNewLinesTestCase(
                    title, input, page_escape_nl, filename, line, setup,
                    teardown, context, mpctx)
            if outline:
                outline = ProductOutlineTestCase(
                    title, input, outline, filename, line, setup,
                    teardown, context, mpctx)
            for tc in [page, oneliner, page_escape_nl, outline]:
                if tc:
                    suite.addTest(tc)
    if data:
        add_test_cases(data, file)
    else:
        for f in ('wiki-tests.txt', 'wikicreole-tests.txt'):
            testfile = os.path.join(os.path.split(file)[0], f)
            if os.path.exists(testfile):
                data = open(testfile, 'r').read().decode('utf-8')
                add_test_cases(data, testfile)
            else:
                print 'no ', testfile
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

