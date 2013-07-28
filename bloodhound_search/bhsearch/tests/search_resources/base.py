#!/usr/bin/env python
# -*- coding: UTF-8 -*-

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

from trac.test import MockPerm
from trac.web import Href
from trac.wiki import format_to_html

from bhsearch.search_resources.base import SimpleSearchWikiSyntaxFormatter
from bhsearch.tests import unittest
from bhsearch.tests.base import BaseBloodhoundSearchTest


class SimpleSearchWikiSyntaxFormatterTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        super(SimpleSearchWikiSyntaxFormatterTestCase, self).setUp(
            create_req=True,
        )
        self.text_formatter = SimpleSearchWikiSyntaxFormatter(self.env)


    def test_can_format_header(self):
        wiki_content = """= Header #overview
        some text"""
        result = self._call_format(wiki_content)
        self.assertEqual("Header overview some text", result)

    def test_can_format_code(self):
        wiki_content = """{{{
        some code
        }}}
        text"""
        result = self._call_format(wiki_content)
        self.assertEqual("some code text", result)

    def test_can_format_anchor(self):
        wiki_content = """sometext1
        [#point1]
        sometext2
        """
        result = self._call_format(wiki_content)
        self.assertEqual("sometext1 point1 sometext2", result)

    def test_can_format_wiki_link(self):
        self.assertEqual(
            "wiki:SomePage p1", self._call_format("[wiki:SomePage p1]"))

    def test_can_format_sample_wiki_link(self):
        self.assertEqual("WikiPage", self._call_format("WikiPage"))


    def test_can_format_makro(self):
        """
        Makro links must be formatted as text
        """
        self.assertEqual(
            "TicketQuery(keywords~x, formattable, colid)",
            self._call_format(
                "[[TicketQuery(keywords=~x, format=table, col=id)]]"))

    def test_can_format_stared_font_makers(self):
        self.assertEqual(
            "bold, italic, WikiCreole style",
            self._call_format(
                "**bold**, //italic//, **//WikiCreole style//**"))


    @unittest.skip("TODO")
    def test_can_format_non_wiki_camel_case(self):
        self.assertEqual("WikiPage", self._call_format("!WikiPage"))

    def _call_format(self, wiki_content):
        result = self.text_formatter.format(wiki_content)
        self.env.log.debug(
            "Input text:\n%s\nFormatted text:\n%s",
            wiki_content,
            result)
        return result

    @unittest.skip("Use for debug purposes only")
    def test_run_html_formatter(self):
        wiki_content = "!WikiSyntax"
        page = self.create_wiki("Dummy wiki", wiki_content)
        from trac.mimeview.api import RenderingContext
        context = RenderingContext(
            page.resource,
            href=Href('/'),
            perm=MockPerm(),
        )
        context.req = None # 1.0 FIXME .req shouldn't be required by formatter
        format_to_html(self.env, context, wiki_content)


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(
        unittest.makeSuite(SimpleSearchWikiSyntaxFormatterTestCase, 'test'))
    return test_suite

if __name__ == '__main__':
    unittest.main()
