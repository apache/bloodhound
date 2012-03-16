
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

"""Helper functions for introspection functionality"""

def subclasses(cls):
    """recursively get subclasses of a class"""
    for sub in cls.__subclasses__():
        for subsub in subclasses(sub):
            yield subsub
        yield sub

def get_enabled_component_subclass(env, cls):
    """if the cls is not enabled, attempts to find a subclass which is"""
    if env.is_component_enabled(cls):
        return cls
    for subcls in subclasses(cls):
        if env.is_component_enabled(subcls):
            return subcls
    return None
