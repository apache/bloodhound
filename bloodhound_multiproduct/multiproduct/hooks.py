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

# these import monkey patch classes required to enable
# multi product support
import multiproduct.env
import multiproduct.dbcursor
import multiproduct.versioncontrol
import multiproduct.ticket.query
import multiproduct.ticket.batch

import re

from trac.core import TracError
from trac.hooks import EnvironmentFactoryBase, RequestFactoryBase
from trac.perm import PermissionCache
from trac.web.href import Href
from trac.web.main import RequestWithSession

PRODUCT_RE = re.compile(r'^/products(?:/(?P<pid>[^/]*)(?P<pathinfo>.*))?')
REDIRECT_DEFAULT_RE = \
    re.compile(r'^/(?P<section>milestone|roadmap|report|newticket|'
               r'ticket|qct|timeline|diff|batchmodify|search|'
               r'(raw-|zip-)?attachment/(ticket|milestone))(?P<pathinfo>.*)')


class MultiProductEnvironmentFactory(EnvironmentFactoryBase):
    def open_environment(self, environ, env_path, global_env, use_cache=False):
        environ.setdefault('SCRIPT_NAME', '')  # bh:ticket:594

        env = pid = None
        path_info = environ.get('PATH_INFO')
        if not path_info:
            return env
        m = PRODUCT_RE.match(path_info)
        if m:
            pid = m.group('pid')

        def create_product_env(product_prefix, script_name, path_info):
            if not global_env._abs_href:
                # make sure global environment absolute href is set before
                # instantiating product environment. This would normally
                # happen from within trac.web.main.dispatch_request
                req = RequestWithSession(environ, None)
                global_env._abs_href = req.abs_href
            try:
                env = multiproduct.env.ProductEnvironment(global_env,
                                                          product_prefix)
            except LookupError:
                # bh:ticket:561 - Display product list and warning message
                env = global_env
            else:
                # shift WSGI environment to the left
                environ['SCRIPT_NAME'] = script_name
                environ['PATH_INFO'] = path_info
            return env

        if pid:
            env = create_product_env(pid,
                                     environ['SCRIPT_NAME'] + '/products/' +
                                     pid,
                                     m.group('pathinfo') or '')
        else:
            redirect = REDIRECT_DEFAULT_RE.match(path_info)
            if redirect:
                from multiproduct.api import MultiProductSystem
                default_product_prefix = \
                    MultiProductSystem(global_env).default_product_prefix
                env = create_product_env(default_product_prefix,
                                         environ['SCRIPT_NAME'],
                                         environ['PATH_INFO'])
        return env


class ProductizedHref(Href):
    PATHS_NO_TRANSFORM = ['chrome',
                          'login',
                          'logout',
                          'prefs',
                          'products',
                          'verify_email',
                          'reset_password',
                          'register',
                          ]
    STATIC_PREFIXES = ['js/',
                       'css/',
                       'img/',
                       ]

    def __init__(self, global_href, base):
        self.super = super(ProductizedHref, self)
        self.super.__init__(base)
        self._global_href = global_href

    def __call__(self, *args, **kwargs):
        if args and isinstance(args[0], basestring):
            if args[0] in self.PATHS_NO_TRANSFORM or \
                    (len(args) == 1 and args[0] == 'admin') or \
                    filter(lambda x: args[0].startswith(x),
                           self.STATIC_PREFIXES):
                return self._global_href(*args, **kwargs)
        return self.super.__call__(*args, **kwargs)


class ProductRequestWithSession(RequestWithSession):
    def __init__(self, env, environ, start_response):
        super(ProductRequestWithSession, self).__init__(environ, start_response)
        self.base_url = env.base_url
        if isinstance(env, multiproduct.env.ProductEnvironment):
            self.href = ProductizedHref(env.parent.href, env.href.base)
            self.abs_href = ProductizedHref(env.parent.abs_href,
                                            env.abs_href.base)


class ProductRequestFactory(RequestFactoryBase):
    def create_request(self, env, environ, start_response):
        return ProductRequestWithSession(env, environ, start_response) \
            if env else RequestWithSession(environ, start_response)
