# -*- coding: utf-8 -*-
#
# Copyright (C) 2010 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.org/wiki/TracLicense.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://trac.edgewall.org/log/.
#
# Author: Joachim Hoessler <hoessler@gmail.com>
from trac.resource import ResourceNotFound
from trac.ticket.api import (ITicketManipulator)
from trac.ticket.model import Ticket
from trac.config import ListOption
from copy import copy
from trac.core import Component, implements
from bhrelations.ticket_links_other import (ITicketLinkController, unique,
                                            TicketLinksSystem)

class LinksProvider(Component):
    """Link controller that provides links as specified in the [ticket-links]
    section in the trac.ini configuration file.
    """

    implements(ITicketLinkController, ITicketManipulator)
    
    PARENT_END = 'parent'
    
    def __init__(self):
        self._links, self._labels, \
        self._validators, self._blockers, \
        self._copy_fields = self._get_links_config()

    def get_ends(self):
        return self._links
    
    def render_end(self, end):
        return self._labels[end]
    
    def is_blocker(self, end):
        return self._blockers[end]
    
    def get_copy_fields(self, end):
        if end in self._copy_fields:
            return self._copy_fields[end]
        else:
            return TicketLinksSystem(self.env).default_copy_fields
    
    def get_validator(self, end):
        return self._validators.get(end)
        
    def prepare_ticket(self, req, ticket, fields, actions):
        pass
        
    def validate_ticket(self, req, ticket):
        action = req.args.get('action')
        ticket_system = TicketLinksSystem(self.env)
        
        for end in ticket_system.link_ends_map:
            check = self.validate_links_exist(ticket, end)
            if check:
                yield None, check
                continue
            
            validator_name = self.get_validator(end)
            if validator_name == 'no_cycle':
                validator = self.validate_no_cycle
            elif validator_name == 'parent_child' and end == self.PARENT_END:
                validator = self.validate_parent
            else:
                validator = self.validate_any
            
            check = validator(ticket, end)
            if check:
                yield None, check
            
            if action == 'resolve' and self.is_blocker(end):
                blockers = self.find_blockers(ticket, end, [])
                if blockers:
                    blockers_str = ', '.join('#%s' % x 
                                             for x in unique(blockers))
                    msg = ("Cannot resolve this ticket because it is "
                           "blocked by '%s' tickets [%s]" 
                           % (end,  blockers_str))
                    yield None, msg
    
    def validate_links_exist(self, ticket, end):
        ticket_system = TicketLinksSystem(self.env)
        links = ticket_system.parse_links(ticket[end])
        bad_links = []
        for link in links:
            try:
                tkt = Ticket(self.env, link)
            except ResourceNotFound:
                bad_links.append(link)
        if bad_links:
            return ("Tickets linked in '%s' do not exist: [%s]" 
                    % (end, ', '.join('#%s' % link for link in bad_links)))
          
    def validate_no_cycle(self, ticket, end):
        cycle = self.find_cycle(ticket, end, [])
        if cycle != None:
            cycle_str = ['#%s'%id for id in cycle]
            return 'Cycle in ''%s'': %s' % (self.render_end(end),
                                            ' -> '.join(cycle_str))

    def validate_parent(self, ticket, end):
        cycle_validation = self.validate_no_cycle(ticket, end)
        if cycle_validation: 
            return cycle_validation
        
        ticket_system = TicketLinksSystem(self.env)
        links = ticket_system.parse_links(ticket[end])
        
        multiple_parents = (end == self.PARENT_END and len(links) > 1)
        if multiple_parents:
            parents_str = ', '.join('#%s' % id for id in links)
            return "Multiple links in '%s': #%s -> [%s]" \
                   % (self.render_end(end), ticket.id, parents_str)
    
    def validate_any(self, ticket, end):
        return None
    
    def _get_links_config(self):
        links = []
        labels = {}
        validators = {}
        blockers = {}
        copy_fields = {}
        
        config = self.config['ticket-links']
        for name in [option for option, _ in config.options()
                     if '.' not in option]:
            ends = [e.strip() for e in config.get(name).split(',')]
            if not ends:
                continue
            end1 = ends[0]
            end2 = None
            if len(ends) > 1:
                end2 = ends[1]
            links.append((end1, end2))
            
            label1 = config.get(end1 + '.label') or end1.capitalize()
            labels[end1] = label1
            if end2:
                label2 = config.get(end2 + '.label') or end2.capitalize()
                labels[end2] = label2
            
            validator = config.get(name + '.validator')
            if validator:
                validators[end1] = validator
                if end2:
                    validators[end2] = validator
                
            blockers[end1] = config.getbool(end1 + '.blocks', default=False)
            if end2:
                blockers[end2] = config.getbool(end2 + '.blocks', default=False)
            
            # <end>.copy_fields may be absent or intentionally set empty.
            # config.getlist() will return [] in either case, so check that
            # the key is present before assigning the value
            for end in [end1, end2]:
                if end:
                    cf_key = '%s.copy_fields' % end
                    if cf_key in config:
                        copy_fields[end] = config.getlist(cf_key)
            
        return links, labels, validators, blockers, copy_fields
    
    def find_blockers(self, ticket, field, blockers):
        ticket_system = TicketLinksSystem(self.env)
        links = ticket_system.parse_links(ticket[field])
        for link in links:
            linked_ticket = Ticket(self.env, link)
            if linked_ticket['status'] != 'closed':
                blockers.append(link)
            else:
                self.find_blockers(linked_ticket, field, blockers)
        return blockers
        
    def find_cycle(self, ticket, field, path):
        if ticket.id in path:
            path.append(ticket.id)
            return path

        path.append(ticket.id)

        ticket_system = TicketLinksSystem(self.env)
        links = ticket_system.parse_links(ticket[field])
        for link in links:
            linked_ticket= Ticket(self.env, link)
            cycle = self.find_cycle(linked_ticket, field, copy(path))
            if  cycle != None:
                return cycle
        return None
                
