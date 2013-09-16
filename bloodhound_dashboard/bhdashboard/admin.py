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
import json
import re
from sys import stdout

from trac.admin.api import IAdminCommandProvider, AdminCommandError
from trac.core import Component, implements
from trac.db_default import schema as tracschema
from trac.util.text import printout
from trac.util.translation import _
from trac.wiki.admin import WikiAdmin
from trac.wiki.model import WikiPage
from bhdashboard import wiki

try:
    from multiproduct.model import Product, ProductResourceMap, ProductSetting
except ImportError:
    Product = ProductResourceMap = ProductSetting = None

schema = tracschema[:]
if Product is not None:
    schema.extend([Product._get_schema(), ProductResourceMap._get_schema(),
                   ProductSetting._get_schema()])

structure = dict([(table.name, [col.name for col in table.columns])
                  for table in schema])

# add product for any columns required
for table in ['ticket']:
    structure[table].append('product')

# probably no point in keeping data from these tables
ignored = ['auth_cookie', 'session', 'session_attribute', 'cache']
IGNORED_DB_STRUCTURE = dict([(k, structure[k]) for k in ignored])
DB_STRUCTURE = dict([(k, structure[k]) for k in structure if k not in ignored])


class BloodhoundAdmin(Component):
    """Bloodhound administration commands.
    """

    implements(IAdminCommandProvider)

    # IAdminCommandProvider methods
    def get_admin_commands(self):
        """List available commands.
        """
        yield ('wiki bh-upgrade', '',
               'Move Trac* wiki pages to %s/*' % wiki.GUIDE_NAME,
               None, self._do_wiki_upgrade)

        yield ('devfixture dump', '[filename]',
               """Dumps database to stdout in a form suitable for reloading

               If a filename is not provided, data will be sent standard out.
               """,
               None, self._dump_as_fixture)

        yield ('devfixture load', '<filename> <backedup>',
               """Loads database fixture from json dump file

               You need to specify a filename and confirm that you have backed
               up your data.
               """,
               None, self._load_fixture_from_file)

    def _do_wiki_upgrade(self):
        """Move all wiki pages starting with Trac prefix to unbranded user
        guide pages.
        """
        wiki_admin = WikiAdmin(self.env)
        pages = wiki_admin.get_wiki_list()
        for old_name in pages:
            if old_name.startswith('Trac'):
                new_name = wiki.new_name(old_name)
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
        self._do_wiki_rename_links('[[TracGuideToc]]', '[[UserGuideToc]]')

    def _do_wiki_rename_links(self, old_name, new_name):
        if old_name.startswith('[[') and old_name.endswith(']]'):
            pattern = r'%s'
        else:
            pattern = r'\b%s\b'
        with self.env.db_transaction as db:
            pages = db("""SELECT name, text FROM wiki
                          WHERE text %s
                       """ % db.like(),
                       ('%' + db.like_escape(old_name) + '%',))
            for name, text in pages:
                db("""UPDATE wiki
                      SET text=%s
                      WHERE name=%s
                    """, (re.sub(pattern % re.escape(old_name),
                                 new_name, text), name))

    def _get_tdump(self, db, table, fields):
        """Dumps all the data from a table for a known set of fields"""
        return db("SELECT %s from %s" % (','.join([db.quote(f) for f in fields]),
                                         db.quote(table)))

    def _dump_as_fixture(self, *args):
        """Dumps database to a json fixture"""
        def dump_json(fp):
            """Dump to json given a file"""
            with self.env.db_query as db:
                data = [(k, v, self._get_tdump(db, k, v))
                        for k, v in DB_STRUCTURE.iteritems()]
                jd = json.dumps(data, sort_keys=True, indent=2,
                                separators=(',', ':'))
                fp.write(jd)

        if len(args):
            f = open(args[0], mode='w+')
            dump_json(f)
            f.close()
        else:
            dump_json(stdout)

    def _load_fixture_from_file(self, fname):
        """Calls _load_fixture with an open file"""
        try:
            fp = open(fname, mode='r')
            self._load_fixture(fp)
            fp.close()
        except IOError:
            printout(_("The file '%(fname)s' does not exist", fname=fname))

    def _load_fixture(self, fp):
        """Extract fixture data from a file like object, expecting json"""
        # Only delete if we think it unlikely that there is data to lose
        with self.env.db_query as db:
            if db('SELECT * FROM ' + db.quote('ticket')):
                printout(_("This command is only intended to run on fresh "
                           "environments as it will overwrite the database.\n"
                           "If it is safe to lose bloodhound data, delete the "
                           "environment and re-run python bloodhound_setup.py "
                           "before attempting to load the fixture again."))
                return
        data = json.load(fp)
        with self.env.db_transaction as db:
            for tab, cols, vals in data:
                db("DELETE FROM " + db.quote(tab))
            for tab, cols, vals in data:
                printout("Populating %s table" % tab)
                db.executemany("INSERT INTO %s (%s) VALUES (%s)"
                               % (db.quote(tab),
                                  ','.join([db.quote(c) for c in cols]),
                                  ','.join(['%s']*len(cols))),
                               vals)
                printout("%d records added" % len(vals))
