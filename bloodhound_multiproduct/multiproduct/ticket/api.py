
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

"""Multiproduct changes to the ticket api"""
from trac.core import Component, implements
from trac.ticket.api import ITicketFieldProvider

from trac.util.translation import N_

from multiproduct.model import Product

class ProductTicketFields(Component):
    """Fields added to the ticket system for product support"""
    
    implements(ITicketFieldProvider)
    
    def get_select_fields(self):
        """Product select fields"""
        return [(35, {'name': 'product', 'label': N_('Product'), 
                      'cls': Product, 'optional': True})]
    
    def get_radio_fields(self):
        """Product radio fields"""
        return []
