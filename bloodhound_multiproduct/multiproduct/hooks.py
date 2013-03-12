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

# these two imports monkey patch required classes
import multiproduct.env
import multiproduct.dbcursor

import re

from trac.hooks import EnvironmentFactoryBase, RequestFactoryBase
from trac.web.main import RequestWithSession
from trac.web.href import Href

PRODUCT_RE = re.compile(r'^/products/(?P<pid>[^/]*)(?P<pathinfo>.*)')

class MultiProductEnvironmentFactory(EnvironmentFactoryBase):
    def open_environment(self, environ, env_path, global_env, use_cache=False):
        env = pid = None
        path_info = environ.get('PATH_INFO')
        if not path_info:
            return env
        m = PRODUCT_RE.match(path_info)
        if m:
            pid = m.group('pid')
        if pid:
            if not global_env._abs_href:
                # make sure global environment absolute href is set before
                # instantiating product environment. This would normally
                # happen from within trac.web.main.dispatch_request
                req = RequestWithSession(environ, None)
                global_env._abs_href = req.abs_href
            env = multiproduct.env.ProductEnvironmentFactory(global_env, pid)
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
        super(ProductizedHref, self).__init__(base)
        self._global_href = global_href

    def __call__(self, *args, **kwargs):
        if args:
            if args[0] in self.PATHS_NO_TRANSFORM or \
               (len(args) == 1 and args[0] == 'admin') or \
               filter(lambda x: args[0].startswith(x), self.STATIC_PREFIXES):
                return self._global_href(*args, **kwargs)
        return super(ProductizedHref, self).__call__(*args, **kwargs)

class ProductRequestWithSession(RequestWithSession):
    def __init__(self, env, environ, start_response):
        super(ProductRequestWithSession, self).__init__(environ, start_response)
        self.base_url = env.base_url
        self.href = ProductizedHref(self.href, env.href.base)
        self.abs_href = ProductizedHref(self.abs_href, env.abs_href.base)

class ProductRequestFactory(RequestFactoryBase):
    def create_request(self, env, environ, start_response):
        if isinstance(env, multiproduct.env.ProductEnvironment):
            return ProductRequestWithSession(env, environ, start_response)
        else:
            return RequestWithSession(environ, start_response)