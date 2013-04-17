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

"""
    This module contains copied pieces of code from the Trac ticket-links
    branch, which is licensed under the the same license as Trac
    (http://trac.edgewall.org/wiki/TracLicense).
    The branch code can be found on
    https://hg.edgewall.org/trac/topic/ticket-links.

    Find more information on trac-links on
    http://trac.edgewall.org/wiki/TracDev/Proposals/TicketLinks
"""
import re
from trac.core import Interface, Component, ExtensionPoint, implements
from trac.config import ListOption
from trac.ticket import Ticket
from trac.ticket.api import ITicketFieldProvider


# Copied from trac/ticket/api.py,
class ITicketLinkController(Interface):

    def get_ends():
        """returns iterable of '(end1, end2)' tuples that make up a link.
        'end2' can be None for unidirectional links."""

    def render_end(end):
        """returns label"""

    def is_blocker(end):
        """Return True if tickets linked by end block closing.
        """
    def get_copy_fields(end):
        """Return an iterable of field names populated in a new ticket created
        as a linked ticket."""

# Copied from trac/util/__init__.py
def unique(seq):
    """Yield unique elements from sequence of hashables, preserving order.
    (New in 0.13)
    """
    seen = set()
    return (x for x in seq if x not in seen and not seen.add(x))

class TicketLinksSystem(Component):
    implements(ITicketFieldProvider)

    link_controllers = ExtensionPoint(ITicketLinkController)

    default_copy_fields = ListOption(
        'ticket',
        'default_copy_fields',
        [],
        doc="""Default fields populated for newly created linked tickets.""")


    # regular expression to match links
    NUMBERS_RE = re.compile(r'\d+', re.U)

    def __init__(self):
        self.link_ends_map = {}
        for controller in self.link_controllers:
            for end1, end2 in controller.get_ends():
                self.link_ends_map[end1] = end2
                if end2 is not None:
                    self.link_ends_map[end2] = end1

    def parse_links(self, value):
        if not value:
            return []
        return list(unique(int(id) for id in self.NUMBERS_RE.findall(value)))

    #ITicketFieldProvider methods
    def get_select_fields(self):
        return []

    def get_radio_fields(self):
        return []

    def get_raw_fields(self):
        fields = []
        for controller in self.link_controllers:
            for end1, end2 in controller.get_ends():
                self._add_link_field(end1, controller, fields)
                if end2 != None and end2 != end1:
                    self._add_link_field(end2, controller, fields)
        return fields

    def _add_link_field(self, end, controller, fields):
        label = controller.render_end(end)
        copy_fields = controller.get_copy_fields(end)
        if end in [f['name'] for f in fields]:
            self.log.warning('Duplicate field name "%s" (ignoring)', end)
            return
        field = {'name': end, 'type': 'link', 'label': label,
                 'link': True, 'format': 'wiki', 'copy_fields': copy_fields}
        fields.append(field)




class TicketLinksModel(Component):

    def populate_from(self, ticket, tkt_id, link_field_name=None,
                            copy_field_names=None):
        """Populate the ticket with 'suitable' values from another ticket.
        """
        ticket_sys = TicketLinksSystem(self.env)
        field_names = [f['name'] for f in ticket.fields]

        if not link_field_name and copy_field_names is None:
            copy_field_names = ticket_sys.default_copy_fields
        elif (link_field_name in ticket_sys.link_ends_map
              and copy_field_names is None):
            link_field = [f for f in ticket.fields
                            if f['name'] == link_field_name][0]
            copy_field_names = link_field['copy_fields']
            ticket[link_field_name] = str('#%s' % tkt_id)

        try:
            tkt_id = int(tkt_id)
        except ValueError:
            return
        # TODO What if tkt_id isn't valid? Currently shows as a TracError
        other_ticket = Ticket(self.env, tkt_id)

        for name in [name for name in copy_field_names if name in field_names]:
            ticket[name] = other_ticket[name]

