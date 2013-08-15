
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

from trac.util.text import unquote_label
from trac.wiki.formatter import LinkFormatter
from trac.core import Component, ComponentMeta

#----------------------------
# Component replacement base
#----------------------------

class ReplacementComponentMeta(ComponentMeta):
    """Component replacement meta class"""
    def __new__(mcs, name, bases, d):
        if bases[0] != Component:
            bases = bases[1:]
            base_class = bases[0]

            # undo what has been done by ComponentMeta.__new___ for the
            # replacement component base class

            # remove implemented interfaces from registry for the base class
            for itf in base_class._implements:
                ComponentMeta._registry[itf] = filter(lambda c: c != base_class,
                                                      ComponentMeta._registry[itf])

            # remove base class from components list
            ComponentMeta._components = filter(lambda c: c != base_class,
                                               ComponentMeta._components)

            base_class._implements = []
            base_class.abstract = True

        return ComponentMeta.__new__(mcs, name, bases, d)

class ReplacementComponent(Component):
    """Base class for components that replace existing trac
    implementations"""
    __metaclass__ = ReplacementComponentMeta

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

#----------------------
# Useful regex
#----------------------

IDENTIFIER = r'(?!\d)\w+'
