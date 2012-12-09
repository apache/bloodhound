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

WikiMacros and WikiProcessors related to dashboard system.
"""

from ast import literal_eval

from genshi.builder import tag

from trac.web.chrome import Chrome
from trac.wiki.api import parse_args
from trac.wiki.macros import WikiMacroBase

from bhdashboard.web_ui import DashboardChrome, DashboardModule

GUIDE_NAME = 'Guide'
RENAME_MAP = {'TracGuide': GUIDE_NAME + '/Index',}

def new_name(name, force=False):
    if name.startswith('Trac'):
        return RENAME_MAP.get(name, GUIDE_NAME + '/' + name[4:])
    else:
        return name

class WidgetMacro(WikiMacroBase):
    """Embed Bloodhound widgets using WikiFormatting.
    """
    #: A gettext domain to translate the macro description
    _domain = None

    #: A macro description
    _description = """Embed Bloodhound widgets using WikiFormatting."""

    def expand_macro(self, formatter, name, content):
        """Render widget contents by re-using wiki markup implementation
        """
        if self.env[DashboardModule] is None:
            return DashboardModule(self.env).alert_disabled()
        largs, kwargs = parse_args(content, strict=True)
        try:
            (widget_name ,) = largs
        except ValueError:
            template = 'widget_alert.html'
            data = {
                    'msgtype' : 'error',
                    'msglabel' : 'Error',
                    'msgbody' : tag('Expected ', tag.code(1), 
                            ' positional argument (i.e. widget name), but got ',
                            tag.code(len(largs)), ' instead'),
                    'msgdetails' : [
                            ('Macro name', tag.code('WidgetMacro')),
                            ('Arguments', ', '.join(largs) if largs \
                                    else tag.span('None', class_='label')),
                        ],
                }
        else:
            widget_name = widget_name.strip()
            wopts = {} ; wargs = {}

            def parse_literal(value):
                try:
                    return literal_eval(value)
                except (SyntaxError, ValueError):
                    return value

            for argnm, value in kwargs.iteritems():
                if argnm.startswith('wo_'):
                    wopts[argnm[3:]] = value
                else :
                    wargs[argnm] = parse_literal(value)
            template = 'widget.html'
            data = {
                    'args' : wargs,
                    'bhdb' : DashboardChrome(self.env),
                    'id' : None,
                    'opts' : wopts,
                    'widget' : widget_name
                }
        return Chrome(self.env).render_template(
                formatter.req, template, data, fragment=True)

