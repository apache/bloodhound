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


def using_multiproduct(env):
    return hasattr(env, 'parent')


def get_global_env(env):
    if not using_multiproduct(env) or env.parent is None:
        return env
    else:
        return env.parent


class GlobalProduct(object):
    prefix = ""
    name = ""
GlobalProduct = GlobalProduct()


def get_product(env):
    if not using_multiproduct(env) or env.parent is None:
        return GlobalProduct
    else:
        return env.product


def instance_for_every_env(env, cls):
    if not using_multiproduct(env):
        return [cls(env)]
    else:
        global_env = get_global_env(env)
        return [cls(global_env)] + \
               [cls(env) for env in global_env.all_product_envs()]


# Compatibility code for `ComponentManager.is_enabled`
# (available since Trac 0.12)
def is_enabled(env, cls):
    """Return whether the given component class is enabled.

    For Trac 0.11 the missing algorithm is included as fallback.
    """
    try:
        return env.is_enabled(cls)
    except AttributeError:
        if cls not in env.enabled:
            env.enabled[cls] = env.is_component_enabled(cls)
        return env.enabled[cls]
