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

"""Core Bloodhound Search components"""

from trac.core import *

class BloodhoundQuerySystem(Component):
    """Implements core query functionality.
    """

    def query(self, query, sort = None, boost = None, filters = None,
              facets = None, start = 0, rows = None):
        """Return query result from on underlying backend.

        Arguments:
        query -- query string e.g. “bla status:closed” or a parsed
            representation of the query.
        sort -- optional sorting
        boost -- optional list of fields with boost values e.g.
            {“id”: 1000, “subject” :100, “description”:10}.
        filters -- optional list of terms. Usually can be cached by underlying
            search framework. For example {“type”: “wiki”}
        facets - optional list of facet terms, can be field or expression.
        start, rows -- paging support

        The result is returned as the following dictionary: {
            "docs": [
                {
                    "id": "ticket:123",
                    "resource_id": "123",
                    "type": "ticket",
                    ...
                }
            ],
            "numFound":3,"
            "start":0,
            "facet_counts":{
                "facet_fields":{
                    "cat":[ "electronics",3, "card",2, "graphics",2, "music",1]
                }
            },
        }
        """
        self.env.log.debug("Receive query request: %s", locals())

        #TODO: add implementation here
        dummy_result = dict(docs = [
            dict(
                resource_id = "123",
                summary = "Dummy result for query: " + (query or ''),
            )
        ])
        return dummy_result

class BloodhoundIndexSystem(Component):
    """Implements core indexing functionality, provides methods for
    adding and deleting documents form index.
    """

    def rebuild_index(self):
        """Erase the index if it exists. Then create a new index from scratch.
        """
        pass

    def optimize(self):
        """Optimize underlying index"""
        pass

    def add_doc(self, doc):
        """Add a document to underlying search backend.

        The doc must be dictionary with obligatory "type" field
        """
        pass

    def delete_doc(self, doc):
        """Add a document from underlying search backend.

        The doc must be dictionary with obligatory "type" field
        """
        pass

