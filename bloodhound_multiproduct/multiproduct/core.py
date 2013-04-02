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

from trac.core import ComponentMeta, ExtensionPoint


class MultiProductExtensionPoint(ExtensionPoint):
    """Marker class for multiproduct extension points in components."""

    def extensions(self, component):
        """Return a multiproduct aware list of components that declare to
        implement the extension point interface.

        When accessed in product environment, only components for that
        environment are returned.

        When accessed in global environment, a separate instance will be
        returned for global and each of the product environments.
        """
        compmgr = component.compmgr
        if not hasattr(compmgr, 'parent') or compmgr.parent is not None:
            return \
                super(MultiProductExtensionPoint, self).extensions(component)

        classes = ComponentMeta._registry.get(self.interface, ())
        components = [component.compmgr[cls] for cls in classes]
        components += [
            env[cls]
            for cls in classes
            for env in component.compmgr.all_product_envs()
        ]
        return [c for c in components if c]
