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

import os
import imp
import inspect

import pkg_resources

from trac.config import Configuration
from trac.env import open_environment
from trac.util.concurrency import threading
from trac.web.api import RequestDone
from trac.web.href import Href
from trac.web.main import RequestWithSession


__all__ = ['environment_factory', 'install_global_hooks']

class EnvironmentFactoryBase(object):
    def open_environment(self, environ, env_path, global_env, use_cache=False):
        raise NotImplementedError("Must override method 'open_environment'")

class RequestFactoryBase(object):
    def create_request(self, env, environ, start_response):
        raise NotImplementedError("Must override method 'create_request'")

def _get_plugins_dir(env_path):
    return os.path.normcase(os.path.realpath(os.path.join(env_path, 'plugins')))

def _get_config(env_path):
    return Configuration(os.path.join(env_path, 'conf', 'trac.ini'),
                         {'envname': os.path.basename(env_path)})

def _hook_load(env_path, hook_path):
    hook_name = os.path.basename(hook_path[:-3])
    plugins_dir = _get_plugins_dir(env_path)
    load_path = os.path.join(plugins_dir, hook_path)
    module = imp.load_source(hook_name, load_path)
    return module

def _get_hook_class(env_path, hook_path, class_type):
    module = _hook_load(env_path, hook_path)
    for (name, cls) in inspect.getmembers(module, inspect.isclass):
        if issubclass(cls, class_type) and \
           not cls is class_type:
            return cls
    return None

_global_hooks_installed = False
_global_hooks_lock = threading.Lock()

def install_global_hooks():
    global _global_hooks_installed, _global_hooks_lock
    if _global_hooks_installed:
        return
    _global_hooks_lock.acquire()
    try:
        if not _global_hooks_installed:
            try:
                # TODO: this is currently hardcoded, maybe it could be made configurable in the future
                import multiproduct.hooks
            except:
                pass
            _global_hooks_installed = True
    finally:
        _global_hooks_lock.release()
    return

def environment_factory(env):
    hook_path = env.config.get('trac', 'environment_factory', default=None)
    return _get_hook_class(env.path, hook_path, EnvironmentFactoryBase) if hook_path else None

def request_factory(env):
    hook_path = env.config.get('trac', 'request_factory', default=None)
    return _get_hook_class(env.path, hook_path, RequestFactoryBase) if hook_path else None

class BootstrapHandlerBase(object):
    """Objects responsible for loading the target environment and
    request objects used in subsequent dispatching. 
    """
    def open_environment(self, environ, start_response):
        """Load and initialize target Trac environment involved in request
        dispatching.

        The following WSGI entries will also be present in `environ` dict:

        ||= WSGI variable =||= Environment variable =||= Comment =||
        || trac.env_path || TRAC_ENV || See wiki:TracModWSGI ||
        || trac.env_parent_dir || TRAC_ENV_PARENT_DIR || See wiki:TracModWSGI||
        || trac.env_index_template || TRAC_ENV_INDEX_TEMPLATE || See wiki:TracInterfaceCustomization ||
        || trac.template_vars || TRAC_TEMPLATE_VARS || See wiki:TracInterfaceCustomization ||
        || trac.locale ||  || Target locale ||
        || trac.base_url || TRAC_BASE_URL || Trac base URL hint ||

        A new entry named 'trac.env_name' identifying environment SHOULD be
        added (e.g. used by tracd to choose authentication realms). 
        As a side-effect the WSGI environment dict (i.e. `environ`) may be
        modified in many different ways to prepare it for subsequent
        dispatching.

        This method may handle the request (e.g. render environment index page)
        in case environment lookup yields void results. In that case it MUST 
        invoke WSGI `write` callable returned by `start_response` and raise 
        `trac.web.api.RequestDone` exception.

        :param environ: WSGI environment dict
        :param start_response: WSGI callback for starting the response
        :return: environment object
        :throws RequestDone: if the request is fully processed while loading
                             target environment e.g. environment index page
        :throws EnvironmentError: if it is impossible to find a way to locate
                                  target environment e.g. TRAC_ENV and 
                                  TRAC_ENV_PARENT_DIR both missing
        :throws Exception: any other exception will be processed by the caller 
                           in order to send a generic error message back to
                           the HTTP client
        """
        raise NotImplementedError("Must override method 'open_environment'")

    def default_probe_environment(self, environ):
        """By default it will invoke `open_environment` and discard the
        resulting environment object. This approach is generic but not
        efficient. Should be overridden whenever possible. 
        """
        # If the expected configuration keys aren't found in the WSGI environment,
        # try looking them up in the process environment variables
        environ.setdefault('trac.env_path', os.getenv('TRAC_ENV'))
        environ.setdefault('trac.env_parent_dir',
                           os.getenv('TRAC_ENV_PARENT_DIR'))
        environ.setdefault('trac.env_index_template',
                           os.getenv('TRAC_ENV_INDEX_TEMPLATE'))
        environ.setdefault('trac.template_vars',
                           os.getenv('TRAC_TEMPLATE_VARS'))
        environ.setdefault('trac.locale', '')
        environ.setdefault('trac.base_url',
                           os.getenv('TRAC_BASE_URL'))

        try:
            self.open_environment(environ, 
                                  lambda status, headers: (lambda data: None))
        except Exception:
            # Handle all exceptions; else potential HTTP protocol violation
            pass

    def probe_environment(self, environ):
        """This method is aimed at providing a lightweight version of
        `open_environment` by solely applying upon `environ` the side effects 
        needed to dispatch the request in environment context.

        By default it will invoke `open_environment` and discard the
        resulting environment object. Specialized versions will have the chance
        to implement more efficient strategies in case environment
        instantiation may be avoided. 

        :return: None
        """
        self.default_probe_environment(environ)
        
    def create_request(self, env, environ, start_response):
        """Instantiate request object used in subsequent request dispatching
        
        :param env: target Trac environment returned by `open_environment`
        :param environ: WSGI environment dict
        :param start_response: WSGI callback for starting the response
        """
        raise NotImplementedError("Must override method 'create_request'")


class DefaultBootstrapHandler(BootstrapHandlerBase):
    """Default bootstrap handler
    
    - Load environment based on URL path.
    - Instantiate RequestWithSession
    
    Notice: This class is a straightforward refactoring of factories
    implementation.
    """
    global_env = None

    def open_environment(self, environ, start_response):
        env_path = environ.get('trac.env_path')
        if env_path:
            environ['trac.env_name'] = os.path.basename(env_path)
        else:
            env_parent_dir = environ.get('trac.env_parent_dir')
            env_paths = environ.get('trac.env_paths')
            if env_parent_dir or env_paths:
                # The first component of the path is the base name of the
                # environment
                path_info = environ.get('PATH_INFO', '').lstrip('/').split('/')
                env_name = path_info.pop(0)
    
                if not env_name:
                    # No specific environment requested, so render an environment
                    # index page
                    send_project_index(environ, start_response, env_parent_dir,
                                       env_paths)
                    raise RequestDone

                environ['trac.env_name'] = env_name
                errmsg = None
    
                # To make the matching patterns of request handlers work, we append
                # the environment name to the `SCRIPT_NAME` variable, and keep only
                # the remaining path in the `PATH_INFO` variable.
                script_name = environ.get('SCRIPT_NAME', '')
                try:
                    script_name = unicode(script_name, 'utf-8')
                    # (as Href expects unicode parameters)
                    environ['SCRIPT_NAME'] = Href(script_name)(env_name)
                    environ['PATH_INFO'] = '/' + '/'.join(path_info)
    
                    if env_parent_dir:
                        env_path = os.path.join(env_parent_dir, env_name)
                    else:
                        env_path = get_environments(environ).get(env_name)
    
                    if not env_path or not os.path.isdir(env_path):
                        errmsg = 'Environment not found'
                except UnicodeDecodeError:
                    errmsg = 'Invalid URL encoding (was %r)' % script_name
    
                if errmsg:
                    write = start_response('404 Not Found',
                                   [('Content-Type', 'text/plain'),
                                    ('Content-Length', str(len(errmsg)))])
                    write(errmsg)
                    raise RequestDone
    
        if not env_path:
            raise EnvironmentError('The environment options "TRAC_ENV" or '
                                   '"TRAC_ENV_PARENT_DIR" or the mod_python '
                                   'options "TracEnv" or "TracEnvParentDir" are '
                                   'missing. Trac requires one of these options '
                                   'to locate the Trac environment(s).')
        run_once = environ['wsgi.run_once']
    
        env = None
        self.global_env = global_env = None
        try:
            self.global_env = global_env = open_environment(env_path, use_cache=not run_once)
            factory = environment_factory(global_env)
            factory_env = factory().open_environment(environ, env_path, global_env, use_cache=not run_once) if factory \
                            else None
            env = factory_env if factory_env else global_env
        except Exception:
            raise
        return env

    def create_request(self, env, environ, start_response):
        factory = None
        try:
            factory = request_factory(self.global_env)
        except Exception:
            pass
        return factory().create_request(env, environ, start_response) if factory \
                else RequestWithSession(environ, start_response)

default_bootstrap_handler = DefaultBootstrapHandler()

def load_bootstrap_handler(bootstrap_ep, log=None):
    """Load handler for environment lookup and instantiation of request objects

    :param bootstrap_ep: entry point specification
    :param log: file-like object used to report errors
    """
    bootstrap = None
    if bootstrap_ep:
        try:
            ep = pkg_resources.EntryPoint.parse('x = ' + bootstrap_ep)
            bootstrap = ep.load(require=False)
        except Exception, e:
            if log:
                log.write("[FAIL] [Trac] entry point '%s'. Reason %s" %
                          (bootstrap_ep, repr(exception_to_unicode(e))))
    if bootstrap is None:
        bootstrap = default_bootstrap_handler
    return bootstrap


# Recursive imports
from trac.web.main import send_project_index, get_environments
