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


r"""Improved search and query plugin for Apache(TM) Bloodhound

Add free text search and query plugin to Bloodhound sites.
"""

# Ignore errors to avoid Internal Server Errors
from trac.core import TracError
TracError.__str__ = lambda self: unicode(self).encode('ascii', 'ignore')

try:
    # pylint: disable=wildcard-import
    from bhsearch import *
    msg = 'Ok'
except Exception, exc:
#    raise
    msg = "Exception %s raised: '%s'" % (exc.__class__.__name__, str(exc))

BHSEARCH_CONFIG_SECTION = "bhsearch"
