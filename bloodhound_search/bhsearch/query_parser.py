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

r"""Provides Bloodhound Search query parsing functionality"""

from bhsearch.api import IQueryParser, IMetaKeywordParser, ISearchParticipant
from bhsearch.whoosh_backend import WhooshBackend
from trac.config import ExtensionPoint
from trac.core import Component, implements
from whoosh import query, qparser
from whoosh.qparser import MultifieldParser


class MetaKeywordNode(qparser.GroupNode):
    def __init__(self, group_node=None, **kwargs):
        nodes = group_node.nodes if group_node else []
        super(MetaKeywordNode, self).__init__(nodes, kwargs=kwargs)


class MetaKeywordPlugin(qparser.TaggingPlugin):
    priority = 0
    expr = r"[$](?P<text>[^ \t\r\n]+)(?= |$|\))"
    nodetype = qparser.syntax.WordNode

    def __init__(self, meta_keyword_parsers=(), context=None):
        super(MetaKeywordPlugin, self).__init__()
        self.meta_keyword_parsers = meta_keyword_parsers
        self.context = context

    def match(self, parser, text, pos):
        match = qparser.TaggingPlugin.match(self, parser, text, pos)
        if match is None:
            return

        candidate = match.text
        for meta_keyword_parser in self.meta_keyword_parsers:
            expanded_meta_keyword = meta_keyword_parser.match(candidate,
                                                              self.context)
            if expanded_meta_keyword is not None:
                node = MetaKeywordNode(parser.tag(expanded_meta_keyword))
                return node.set_range(match.startchar, match.endchar)

    def filters(self, parser):
        # must execute before GroupPlugin with priority 0
        return [(self.unroll_meta_keyword_nodes, -100)]

    def unroll_meta_keyword_nodes(self, parser, group):
        newgroup = group.empty_copy()
        for node in group:
            if isinstance(node, MetaKeywordNode):
                newgroup.extend(self.unroll_meta_keyword_nodes(parser, node))
            elif isinstance(node, qparser.GroupNode):
                newgroup.append(self.unroll_meta_keyword_nodes(parser, node))
            else:
                newgroup.append(node)
        return newgroup


class DefaultQueryParser(Component):
    implements(IQueryParser)

    #todo: make field boost configurable e.g. read from config setting.
    #This is prototype implementation ,the fields boost must be tuned later
    field_boosts = dict(
        id = 6,
        name = 6,
        type = 2,
        summary = 5,
        author = 3,
        milestone = 2,
        keywords = 2,
        component = 2,
        status = 2,
        content = 1,
        changes = 1,
        message = 1,
        query_suggestion_basket = 0,
        relations = 1,
    )

    meta_keyword_parsers = ExtensionPoint(IMetaKeywordParser)

    def parse(self, query_string, context=None):
        parser = self._create_parser(context)
        query_string = query_string.strip()
        if query_string == "" or query_string == "*" or query_string == "*:*":
            return query.Every()
        query_string = unicode(query_string)
        parsed_query = parser.parse(query_string)
        parsed_query.original_query_string = query_string
        return parsed_query

    def parse_filters(self, filters):
        """Parse query filters"""
        if not filters:
            return None
        parsed_filters = [self._parse_filter(filter) for filter in filters]
        return query.And(parsed_filters).normalize()

    def _parse_filter(self, filter):
        return self.parse(unicode(filter))

    def _create_parser(self, context):
        parser = MultifieldParser(
            self.field_boosts.keys(),
            WhooshBackend.SCHEMA,
            fieldboosts=self.field_boosts
        )
        parser.add_plugin(
            MetaKeywordPlugin(meta_keyword_parsers=self.meta_keyword_parsers,
                              context=context)
        )
        return parser


class DocTypeMetaKeywordParser(Component):
    implements(IMetaKeywordParser)

    search_participants = ExtensionPoint(ISearchParticipant)

    def match(self, text, context):
        # pylint: disable=unused-argument
        documents = [p.get_participant_type()
                     for p in self.search_participants]
        if text in documents:
            return u'type:%s' % text


class ResolvedMetaKeywordParser(Component):
    implements(IMetaKeywordParser)

    def match(self, text, context):
        # pylint: disable=unused-argument
        if text == u'resolved':
            return u'status:(resolved OR closed)'


class UnResolvedMetaKeywordParser(Component):
    implements(IMetaKeywordParser)

    def match(self, text, context):
        # pylint: disable=unused-argument
        if text == u'unresolved':
            return u'NOT $resolved'


class MeMetaKeywordParser(Component):
    implements(IMetaKeywordParser)

    def match(self, text, context):
        if text == u'me':
            username = unicode(context.req.authname)
            return username


class MyMetaKeywordParser(Component):
    implements(IMetaKeywordParser)

    def match(self, text, context):
        # pylint: disable=unused-argument
        if text == u'my':
            return u'owner:$me'
