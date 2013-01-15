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

from config import Configuration
from util.concurrency import threading

__all__ = ['environment_factory', 'install_global_hooks']

class EnvironmentFactoryBase(object):
    def open_environment(self, environ, env_path, global_env, use_cache=False):
        return None

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
