
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

"""Multiproduct support - changes to the ticket api"""
import re
from trac.ticket.api import TicketSystem

from trac.cache import cached
from trac.util.translation import N_

from trac.ticket import model
from multiproduct.model import Product

class ProductTicketSystem(TicketSystem):
    """Multiproduct Overrides for the TicketSystem component"""
    
    @cached
    def fields(self, db):
        """Return the list of fields available for tickets."""
        
        fields = []
        
        # Basic text fields
        fields.append({'name': 'summary', 'type': 'text',
                       'label': N_('Summary')})
        fields.append({'name': 'reporter', 'type': 'text',
                       'label': N_('Reporter')})
        
        # Owner field, by default text but can be changed dynamically 
        # into a drop-down depending on configuration (restrict_owner=true)
        field = {'name': 'owner', 'label': N_('Owner')}
        field['type'] = 'text'
        fields.append(field)
        
        # Description
        fields.append({'name': 'description', 'type': 'textarea',
                       'label': N_('Description')})
        
        # Default select and radio fields
        selects = [('type', N_('Type'), model.Type),
                   ('status', N_('Status'), model.Status),
                   ('priority', N_('Priority'), model.Priority),
                   ('product', N_('Product'), Product),
                   ('milestone', N_('Milestone'), model.Milestone),
                   ('component', N_('Component'), model.Component),
                   ('version', N_('Version'), model.Version),
                   ('severity', N_('Severity'), model.Severity),
                   ('resolution', N_('Resolution'), model.Resolution)]
        for name, label, cls in selects:
            options = [val.name for val in cls.select(self.env, db=db)]
            if not options:
                # Fields without possible values are treated as if they didn't
                # exist
                continue
            field = {'name': name, 'type': 'select', 'label': label,
                     'value': getattr(self, 'default_' + name, ''),
                     'options': options}
            if name in ('status', 'resolution'):
                field['type'] = 'radio'
                field['optional'] = True
            elif name in ('product', 'milestone', 'version'):
                field['optional'] = True
            fields.append(field)
        
        # Advanced text fields
        fields.append({'name': 'keywords', 'type': 'text',
                       'label': N_('Keywords')})
        fields.append({'name': 'cc', 'type': 'text', 'label': N_('Cc')})
        
        # Date/time fields
        fields.append({'name': 'time', 'type': 'time',
                       'label': N_('Created')})
        fields.append({'name': 'changetime', 'type': 'time',
                       'label': N_('Modified')})
        
        for field in self.get_custom_fields():
            if field['name'] in [f['name'] for f in fields]:
                self.log.warning('Duplicate field name "%s" (ignoring)',
                                 field['name'])
                continue
            if field['name'] in self.reserved_field_names:
                self.log.warning('Field name "%s" is a reserved name '
                                 '(ignoring)', field['name'])
                continue
            if not re.match('^[a-zA-Z][a-zA-Z0-9_]+$', field['name']):
                self.log.warning('Invalid name for custom field: "%s" '
                                 '(ignoring)', field['name'])
                continue
            field['custom'] = True
            fields.append(field)
        
        return fields
