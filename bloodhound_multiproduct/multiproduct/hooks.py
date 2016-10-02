# -*- coding: UTF-8 -*-
#
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

# these imports monkey patch classes required to enable
# multi product support

import re

from trac.hooks import EnvironmentFactoryBase, RequestFactoryBase
from trac.web.href import Href
from trac.web.main import RequestWithSession

import multiproduct.env
import multiproduct.dbcursor
import multiproduct.ticket.batch
import multiproduct.ticket.query
import multiproduct.versioncontrol

PRODUCT_RE = re.compile(r'^/products(?:/(?P<pid>[^/]*)(?P<pathinfo>.*))?')


class MultiProductEnvironmentFactory(EnvironmentFactoryBase):
    def open_environment(self, environ, env_path, global_env, use_cache=False):
        # clearing product environment cache - bh:ticket:613
        multiproduct.env.ProductEnvironment.clear_env_cache()
        environ.setdefault('SCRIPT_NAME', '')  # bh:ticket:594

        env = pid = product_path = None
        path_info = environ.get('PATH_INFO')
        if not path_info:
            return env
        m = PRODUCT_RE.match(path_info)
        if m:
            pid = m.group('pid')
            product_path = m.group('pathinfo') or ''

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

        if pid and not (product_path in ('', '/') and
                        environ.get('QUERY_STRING')):
            env = create_product_env(pid,
                                     environ['SCRIPT_NAME'] + '/products/' +
                                     pid, product_path)
            env.config.parse_if_needed()

        return env


class ProductizedHref(Href):
    PATHS_NO_TRANSFORM = ['chrome', 'login', 'logout', 'prefs', 'products',
                          'register',  'reset_password', 'verify_email']
    STATIC_PREFIXES = ['css/', 'img/', 'js/']

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
