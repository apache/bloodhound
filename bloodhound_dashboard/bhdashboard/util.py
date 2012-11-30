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

Helper functions and classes.
"""

from functools import update_wrapper
import inspect
from pkg_resources import get_distribution
from urlparse import urlparse
from wsgiref.util import setup_testing_defaults

from trac.core import Component, implements, ExtensionPoint
from trac.util.text import to_unicode
from trac.web.api import Request
from trac.web.chrome import add_link, Chrome
from trac.web.main import RequestDispatcher

from bhdashboard.api import DashboardSystem, IWidgetProvider, InvalidIdentifier

#------------------------------------------------------
#    Request handling
#------------------------------------------------------

def dummy_request(env, uname=None):
    environ = {}
    setup_testing_defaults(environ)
    environ.update({
                'REQUEST_METHOD' : 'GET',
                'SCRIPT_NAME' : urlparse(str(env._abs_href())).path,
                'trac.base_url' : str(env._abs_href()), 
                })
    req = Request(environ, lambda *args, **kwds: None)
    # Intercept redirection
    req.redirect = lambda *args, **kwds: None
    # Setup user information
    if uname is not None :
        environ['REMOTE_USER'] = req.authname = uname
    
    rd = RequestDispatcher(env)
    chrome = Chrome(env)
    req.callbacks.update({
        'authname': rd.authenticate,
        'chrome': chrome.prepare_request,
        'hdf': getattr(rd, '_get_hdf', None),
        'lc_time': rd._get_lc_time,
        'locale' : getattr(rd, '_get_locale', None),
        'perm': rd._get_perm,
        'session': rd._get_session,
        'tz': rd._get_timezone,
        'form_token': rd._get_form_token
    })
    return req

def merge_links(srcreq, dstreq, exclude=None):
    """Incorporate links in `srcreq` into `dstreq`.
    """
    if exclude is None:
        exclude = ['alternate']
    if 'links' in srcreq.chrome:
        for rel, links in srcreq.chrome['links'].iteritems():
            if rel not in exclude:
                for link in links:
                    add_link(dstreq, rel, **link)

#------------------------------------------------------
#    Widget helpers
#------------------------------------------------------

class WidgetBase(Component):
    """Abstract base class for widgets"""

    implements(IWidgetProvider)
    abstract = True

    def get_widgets(self):
        """Yield the name of the widget based on the class name."""
        name = self.__class__.__name__
        if name.endswith('Widget'):
            name = name[:-6]
        yield name

    def get_widget_description(self, name):
        """Return the subclass's docstring."""
        return to_unicode(inspect.getdoc(self.__class__))

    def get_widget_params(self, name):
        """Return a dictionary containing arguments specification for
        the widget with specified name.
        """
        raise NotImplementedError

    def render_widget(self, context, name, options):
        """Render widget considering given options."""
        raise NotImplementedError

    # Helper methods
    def bind_params(self, name, options, *params):
        return DashboardSystem(self.env).bind_params(options, 
                self.get_widget_params(name), *params)

def check_widget_name(f):
    """Decorator used to wrap methods of widget providers so as to ensure
    widget names will match those listed by `get_widgets` method.
    """
    def widget_name_checker(self, name, *args, **kwargs):
        names = set(self.get_widgets())
        if name not in names: 
            raise InvalidIdentifier('Widget name MUST match any of ' + 
                        ', '.join(names), 
                    title='Invalid widget identifier')
        return f(self, name, *args, **kwargs)
    return widget_name_checker

#------------------------------------------------------
#    Function decorators and wrappers
#------------------------------------------------------

def pretty_wrapper(wrapped, *decorators):
    """Apply multiple decorators to a given function and make the result 
    look like wrapped function.
    """
    wrapper = wrapped
    for f in decorators:
        wrapper = f(wrapper)
    return update_wrapper(wrapper, wrapped)

#------------------------------------------------------
#    Trac core
#------------------------------------------------------

def resolve_ep_class(interface, component, clsnm, **kwargs):
    r"""Retrieve the class implementing an interface (by name)
    """
    ep = ExtensionPoint(interface)
    for c in ep.extensions(component):
        if c.__class__.__name__ == clsnm :
            return c
    else:
        if 'default' in kwargs:
            return kwargs['default']
        else:
            raise LookupError('No match found for class %s implementing %s' % 
                    (clsnm, interface) )

#------------------------------------------------------
#    Context information
#------------------------------------------------------

trac_version = tuple(int(i) for i in get_distribution('Trac').parsed_version \
                            if i.startswith('0'))

# The exact moments (versions) where some things started to change
# in such a manner that break previous test code

trac_tags = (
        (0, 13), # TODO: Find the exact version ( Trac=0.12 ? )
    )

#------------------------------------------------------
#    Miscellaneous
#------------------------------------------------------

def minmax(seq, accessor=lambda x: x):
    """Retrieve lower and upper bounds in a squence
    """
    minval = maxval = None
    seq = iter(seq)
    try:
        minval = maxval = accessor(seq.next())
    except StopIteration:
        pass
    for x in seq:
        value = accessor(x)
        if value > maxval:
            maxval = value
        if value < minval:
            minval = value
    return dict(min=minval, max=maxval)


