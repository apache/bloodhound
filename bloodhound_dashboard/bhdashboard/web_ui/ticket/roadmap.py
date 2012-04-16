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

r"""Roadmap view for Apache(TM) Bloodhound

Customizing roadmap user interface.
"""

__metaclass__ = type

from itertools import izip
import pkg_resources
import re

from genshi.builder import tag
from trac.core import Component, implements
from trac.mimeview.api import Context
from trac.ticket.roadmap import MilestoneModule, RoadmapModule
from trac.util.translation import _
from trac.web.api import IRequestFilter
from trac.web.chrome import add_ctxtnav, add_stylesheet

from bhdashboard.api import DashboardSystem

class BloodhoundMilestoneModule(Component):
    """Override default milestone views.
    """
    implements(IRequestFilter)

    # IRequestFilter methods

    def pre_process_request(self, req, handler):
        """Always returns the request handler unchanged.
        """
        return handler

    def post_process_request(self, req, template, data, content_type):
        """Customize milestone view.
        """
        add_stylesheet(req, 'dashboard/roadmap.css')
        mdl = self.env[MilestoneModule]
        if mdl is not None and mdl.match_request(req):
            return {
                    'milestone_view.html' : 'bhmilestone.html',
                }.get(template, template), data, content_type
        else:
            return template, data, content_type
