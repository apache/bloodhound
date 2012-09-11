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

In this file you'll find part of the tests written to ensure that
dashboard web module works as expected.

Only the tests requiring minimal setup effort are included below. 
This means that the environment used to run these tests contains the 
barely minimal information included in an environment (i.e. only the 
data specified by `trac.db_default.get_data`.).

Once the tests are started all built-in components (except 
trac.versioncontrol.* ) as well as widget system and extensions
are loaded. Besides the following values are (auto-magically)
made available in the global namespace (i.e. provided that 
the test name be written like `|widget_name: Descriptive message`):

  - __tester__  An instance of `unittest.TestCase` representing the 
                test case for the statement under test. Useful 
                when specific assertions (e.g. `assertEquals`) 
                are needed.
  - req         A dummy request object setup for anonymous access.
  - auth_req    A dummy request object setup like if user `murphy` was  
                accessing the site.
  - env         the Trac environment used as a stub for testing purposes.
                This object is an instance of 
                `bhdashboard.tests.EnvironmentStub`.
  - ticket_data A set of tickets used for testing purposes.
"""

#------------------------------------------------------
#    Test artifacts
#------------------------------------------------------

from bhdashboard.tests import trac_version, trac_tags

def test_suite():
  from doctest import NORMALIZE_WHITESPACE, ELLIPSIS, REPORT_UDIFF
  from dutest import MultiTestLoader
  from unittest import defaultTestLoader

  from bhdashboard.tests import DocTestTracLoader, ticket_data

  magic_vars = dict(ticket_data=ticket_data)
  if trac_version < (0, 13): # FIXME: Should it be (0, 12) ?
    kwargs = {'enable': ['trac.[a-uw-z]*', 'tracrpc.*', 'bhdashboard.*']}
  else:
    kwargs = {
            'enable': ['trac.*', 'tracrpc.*', 'bhdashboard.*'],
            'disable': ['trac.versioncontrol.*']
        }

  l = MultiTestLoader(
        [defaultTestLoader, \
          DocTestTracLoader(extraglobs=magic_vars, \
                            default_data=True, \
                            optionflags=ELLIPSIS | REPORT_UDIFF | \
                                        NORMALIZE_WHITESPACE, \
                            **kwargs) \
        ])

  import sys
  return l.loadTestsFromModule(sys.modules[__name__])

#------------------------------------------------------
#    Helper functions
#------------------------------------------------------

from datetime import datetime, time, date
from itertools import izip
from pprint import pprint

from bhdashboard.tests import clear_perm_cache

def prepare_ticket_workflow(tcktrpc, ticket_data, auth_req):
  r"""Set ticket status considering the actions defined in standard 
  ticket workflow. Needed for TracRpc>=1.0.6
  """
  from time import sleep

  TICKET_ACTIONS = {'accepted': 'accept', 'closed' : 'resolve',
                    'assigned': 'reassign'}
  sleep(1)
  for idx, (_, __, td) in enumerate(ticket_data) :
    action = TICKET_ACTIONS.get(td.get('status'))
    if action is not None :
      aux_attrs = {'action' : action}
      aux_attrs.update(td)
      tcktrpc.update(auth_req, idx + 1, "", aux_attrs)
  sleep(1)
  for idx, (_, __, td) in enumerate(ticket_data) :
    tcktrpc.update(auth_req, idx + 1, "", td)

from bhdashboard.web_ui import DashboardModule

__test__ = {
    'Initialization: Report widgets' : r"""
      """,
    'Rendering templates' : r"""
      >>> dbm = DashboardModule(env)
      >>> from trac.mimeview.api import Context
      >>> context = Context.from_request(auth_req)
      
      #FIXME: This won't work. Missing schema

      >>> pprint(dbm.expand_widget_data(context))
      [{'content': <genshi.core.Stream object at ...>, 
      'title': <Element "a">}]
      """,
  }

