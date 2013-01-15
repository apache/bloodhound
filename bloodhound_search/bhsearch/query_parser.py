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

from bhsearch.api import IQueryParser
from bhsearch.whoosh_backend import WhooshBackend
from trac.core import Component, implements
from whoosh.qparser import MultifieldParser

class DefaultQueryParser(Component):
    implements(IQueryParser)

    def parse(self, query_string):
        #todo: make field boost configurable e.g. read from config setting
        #this is prototype implementation ,the fields boost must be tuned later
        field_boosts = dict(
            id = 6,
            type = 2,
            summary = 5,
            author = 3,
            milestone = 2,
            keywords = 2,
            component = 2,
            status = 2,
            content = 1,
            changes = 1,
        )
        parser = MultifieldParser(
            field_boosts.keys(),
            WhooshBackend.SCHEMA,
            fieldboosts=field_boosts
        )
        query_string = unicode(query_string)
        parsed_query = parser.parse(query_string)

        #todo: impelement pluggable mechanizem for query post processing
        #e.g. meta keyword replacement etc.
        return parsed_query

