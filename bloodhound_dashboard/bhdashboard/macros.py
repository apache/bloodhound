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

r"""Bloodhound Macros"""

from genshi.builder import tag
from trac.util.translation import _, cleandoc_
from trac.wiki.api import WikiSystem
from trac.wiki.macros import WikiMacroBase

from bhdashboard.wiki import GUIDE_NAME

class UserGuideTocMacro(WikiMacroBase):
    _description = cleandoc_("""Display a Guide table of contents
    
    This macro provides the table-of-contents specific to the user Guide
    """
    )
    TOC = [('%(guide)s/Index',                    'Index'),
           ('%(guide)s/Install',                  'Installation'),
           ('%(guide)s/InterfaceCustomization',   'Customization'),
           ('%(guide)s/Plugins',                  'Plugins'),
           ('%(guide)s/Upgrade',                  'Upgrading'),
           ('%(guide)s/Ini',                      'Configuration'),
           ('%(guide)s/Admin',                    'Administration'),
           ('%(guide)s/Backup',                   'Backup'),
           ('%(guide)s/Logging',                  'Logging'),
           ('%(guide)s/Permissions' ,             'Permissions'),
           ('%(guide)s/Wiki',                     'The Wiki'),
           ('WikiFormatting',               'Wiki Formatting'),
           ('%(guide)s/Timeline',                 'Timeline'),
           ('%(guide)s/Browser',                  'Repository Browser'),
           ('%(guide)s/RevisionLog',              'Revision Log'),
           ('%(guide)s/Changeset',                'Changesets'),
           ('%(guide)s/Tickets',                  'Tickets'),
           ('%(guide)s/Workflow',                 'Workflow'),
           ('%(guide)s/Roadmap',                  'Roadmap'),
           ('%(guide)s/Query',                    'Ticket Queries'),
           ('%(guide)s/BatchModify',              'Batch Modify'),
           ('%(guide)s/Reports',                  'Reports'),
           ('%(guide)s/Rss',                      'RSS Support'),
           ('%(guide)s/Notification',             'Notification'),
          ]

    def expand_macro(self, formatter, name, args):
        curpage = formatter.resource.id

        # scoped TOC (e.g. TranslateRu/Guide or 0.X/Guide ...)
        prefix = ''
        guideprefix =  GUIDE_NAME + '/'
        data = {'guide': GUIDE_NAME,}
        idx = curpage.find('/')
        if idx > 0:
            prefix = curpage[:idx+1]
        if prefix.endswith(guideprefix):
            prefix = prefix[:len(prefix)-len(guideprefix)]
        ws = WikiSystem(self.env)
        return tag.div(
            tag.h4(_('Table of Contents')),
            tag.ul([tag.li(tag.a(title,
                                 href=formatter.href.wiki(prefix+ref % data),
                                 class_=(not ws.has_page(prefix+ref % data) and
                                         'missing')),
                           class_=(prefix+ref % data== curpage and 'active'))
                    for ref, title in self.TOC]),
            class_='wiki-toc')
