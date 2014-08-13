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

from trac.wiki import WikiSystem, WikiPage
from bhsearch.search_resources.wiki_search import WikiIndexer
from bhsearch.search_resources.base import BaseIndexer

class WikiSearchModel(BaseIndexer):

    def get_entries_for_index(self):
        page_names = WikiSystem(self.env).get_pages()
        for page_name in page_names:
            page = WikiPage(self.env, page_name)
            yield WikiIndexer(self.env).build_doc(page)
