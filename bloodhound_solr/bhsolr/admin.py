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
Module holding the implementation of the IAdminCommandProvider
interface, so that a new trac-admin command is available to be used.
"""

from trac.core import Component, implements
from trac.admin import IAdminCommandProvider
from bhsolr.schema import SolrSchema

class BloodhoundSolrAdmin(Component):
    implements(IAdminCommandProvider)

    """Class implementing the IAdminCommandProvider.

    Provide a new trac-admin command, suitable for use with the
    Bloodhound Solr plugin.
    """

    def get_admin_commands(self):
        """Generate a new trac-admin command.

        Create a trac-admin command for generating a schema.xml file.
        Yields a touple containing the command name for generating a
        Solr schema, the argument description (i.e. the path to where
        the Solr schema should be generated, a help text and the
        callback function that generates the Solr schema.
        """

        yield ('bhsolr generate_schema', '<path>',
               'Generate Solr schema',
               None, SolrSchema(self.env).generate_schema)


