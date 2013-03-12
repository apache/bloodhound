
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

"""Bloodhound multiproduct utility APIs"""

from genshi.builder import tag

from trac import db_default
from trac.util.text import unquote_label
from trac.wiki.formatter import LinkFormatter

class ProductDelegate(object):
    @staticmethod
    def add_product(env, product, keys, field_data):
        from multiproduct.api import MultiProductSystem

        product.update_field_dict(keys)
        product.update_field_dict(field_data)
        product.insert()

        env.log.debug("Adding product info (%s) to tables:" % product.prefix)
        with env.db_direct_transaction as db:
            # create the default entries for this Product from defaults
            for table in db_default.get_data(db):
                if not table[0] in MultiProductSystem.MIGRATE_TABLES:
                    continue

                env.log.debug("  -> %s" % table[0])
                cols = table[1] + ('product', )
                rows = [p + (product.prefix, ) for p in table[2]]
                db.executemany(
                    "INSERT INTO %s (%s) VALUES (%s)" %
                    (table[0], ','.join(cols), ','.join(['%s' for c in cols])),
                    rows)

            # in addition copy global admin permissions (they are
            # not part of the default permission table)
            rows = db("""SELECT username FROM permission WHERE action='TRAC_ADMIN'
                         AND product=''""")
            rows = [(r[0], 'TRAC_ADMIN', product.prefix) for r in rows]
            cols = ('username', 'action', 'product')
            db.executemany("INSERT INTO permission (%s) VALUES (%s)" %
                (','.join(cols), ','.join(['%s' for c in cols])), rows)


#--------------------------
# Custom wiki formatters
#--------------------------

class EmbeddedLinkFormatter(LinkFormatter):
    """Format the inner TracLinks expression corresponding to resources 
    in compound links e.g. product:PREFIX:ticket:1 , global:ticket:1
    """

    def __init__(self, env, context, parent_match=None):
        """Extend initializer signature to accept parent match
        
        @param parent_match: mapping object containing the following keys
                        - ns : namespace of parent resolver
                        - target : target supplied in to parent resolver
                        - label: label supplied in to parent resolver
                        - fullmatch : parent regex match (optional)
        """
        super(EmbeddedLinkFormatter, self).__init__(env, context)
        self.parent_match = parent_match
        self.auto_quote = False

    def match(self, wikitext):
        if self.auto_quote:
            parts = tuple(wikitext.split(':', 1))
            if len(parts) == 2:
                if parts[1]:
                    _wikitext = '%s:"%s"' % parts
                else:
                    _wikitext = '[%s:]' % parts[:1]
            else:
                _wikitext = wikitext
        return super(EmbeddedLinkFormatter, self).match(_wikitext)

    @staticmethod
    def enhance_link(link):
        return link

    def handle_match(self, fullmatch):
        if self.parent_match is None:
            return super(EmbeddedLinkFormatter, self).handle_match(fullmatch)

        for itype, match in fullmatch.groupdict().items():
            if match and not itype in self.wikiparser.helper_patterns:
                # Check for preceding escape character '!'
                if match[0] == '!':
                    # Erroneous expression. Nested link would be escaped 
                    return tag.a(self.parent_match['label'], class_='missing')
                if itype in self.wikiparser.external_handlers:
                    #TODO: Important! Add product prefix in label (when needed?)
                    external_handler = self.wikiparser.external_handlers[itype]
                    link = external_handler(self, match, fullmatch)
                else:
                    internal_handler = getattr(self, '_%s_formatter' % itype)
                    link = internal_handler(match, fullmatch)
                return self.enhance_link(link)

    # Overridden formatter methods
    # TODO : Override more if necessary
    def _shref_formatter(self, match, fullmatch):
        if self.parent_match is None:
            return super(EmbeddedLinkFormatter, self)._shref_formatter(
                    match, fullmatch)
        ns = fullmatch.group('sns')
        target = unquote_label(fullmatch.group('stgt'))
        label = (self.parent_match['label']
                 if self.parent_match['label'] != self.parent_match['target']
                 else target)
        return self._make_link(ns, target, match, label, fullmatch)

    def _lhref_formatter(self, match, fullmatch):
        if self.parent_match is None:
            return super(EmbeddedLinkFormatter, self)._lhref_formatter(
                    match, fullmatch)
        rel = fullmatch.group('rel')
        ns = fullmatch.group('lns')
        target = unquote_label(fullmatch.group('ltgt'))
        label = (self.parent_match['label']
                 if self.parent_match['label'] != self.parent_match['target']
                 else fullmatch.group('label'))
        return self._make_lhref_link(match, fullmatch, rel, ns, target, label)

