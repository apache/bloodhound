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


r"""Project dashboard for Apache(TM) Bloodhound

Administration commands for Bloodhound Dashboard.
"""

from trac.admin.api import IAdminCommandProvider, AdminCommandError
from trac.core import Component, implements
from trac.util.text import printout
from trac.util.translation import _
from trac.wiki.admin import WikiAdmin
from trac.wiki.model import WikiPage

GUIDE_NAME = 'Guide'

class BloodhoundAdmin(Component):
    """Bloodhound administration commands.
    """

    RENAME_MAP = {'TracGuide': GUIDE_NAME + '/Index',}

    implements(IAdminCommandProvider)

    # IAdminCommandProvider methods
    def get_admin_commands(self):
        """List available commands.
        """
        yield ('wiki bh-upgrade', '',
                'Move Trac* wiki pages to %s/*' % GUIDE_NAME,
                None, self._do_wiki_upgrade)

    def _do_wiki_upgrade(self):
        """Move all wiki pages starting with Trac prefix to unbranded user
        guide pages.
        """
        get_new_name = self.RENAME_MAP.get

        wiki_admin = WikiAdmin(self.env)
        pages = wiki_admin.get_wiki_list()
        for old_name in pages:
            if old_name.startswith('Trac'):
                new_name = get_new_name(old_name,
                                        GUIDE_NAME + '/' + old_name[4:])
                if not new_name:
                    continue
                if new_name in pages:
                    printout(_('Ignoring %(page)s : '
                               'The page %(new_page)s already exists',
                               page=old_name, new_page=new_name))
                    continue
                try:
                    wiki_admin._do_rename(old_name, new_name)
                except AdminCommandError, exc:
                    printout(_('Error moving %(page)s : %(message)s',
                            page=old_name, message=unicode(exc)))
                else:
                    # On success, rename links in other pages
                    self._do_wiki_rename_links(old_name, new_name)
                    # On success, insert redirection page
                    redirection = WikiPage(self.env, old_name)
                    redirection.text = _('See [wiki:"%(name)s"].', name=new_name)
                    comment = 'Bloodhound guide update'
                    redirection.save('bloodhound', comment, '0.0.0.0')
        self._do_wiki_rename_links('TracGuideToc', 'UserGuideToc')

    def _do_wiki_rename_links(self, old_name, new_name):
        import re
        with self.env.db_transaction as db:
            pages = db("""SELECT name, text FROM wiki
                          WHERE text %s
                          """ % db.like(),
                              ('%' + db.like_escape(old_name) + '%',))
            for name, text in pages:
                res = db("""UPDATE wiki
                            SET text=%s
                            WHERE name=%s
                            """, 
                         (re.sub(r'\b%s\b' % old_name, new_name, text), name))
