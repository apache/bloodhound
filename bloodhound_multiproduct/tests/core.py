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

import sys
if sys.version < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from trac.core import Interface, implements, Component

from multiproduct.core import MultiProductExtensionPoint

class MultiProductExtensionPointTestCase(unittest.TestCase):
    def setUp(self):
        from trac.core import ComponentManager, ComponentMeta
        self.compmgr = ComponentManager()

        # Make sure we have no external components hanging around in the
        # component registry
        self.old_registry = ComponentMeta._registry
        ComponentMeta._registry = {}

    def tearDown(self):
        # Restore the original component registry
        from trac.core import ComponentMeta
        ComponentMeta._registry = self.old_registry

    def test_with_trac_component_manager(self):
        """No parent attribute, no _all_product_envs method"""
        class ComponentA(Component):
            implements(ITest)

        class ComponentB(Component):
            mp_extension_point = MultiProductExtensionPoint(ITest)

        components = ComponentB(self.compmgr).mp_extension_point
        self.assertEqual(len(components), 1)
        for c in components:
            self.assertIsInstance(c, ComponentA)

    def test_with_global_product_component_manager(self):
        self.compmgr.parent = None
        self.compmgr.all_product_envs = lambda: [self.compmgr, self.compmgr]

        class ComponentA(Component):
            implements(ITest)

        class ComponentB(Component):
            mp_extension_point = MultiProductExtensionPoint(ITest)

        components = ComponentB(self.compmgr).mp_extension_point
        self.assertEqual(len(components), 3)
        for c in components:
            self.assertIsInstance(c, ComponentA)

    def test_with_product_component_manager(self):
        self.compmgr.parent = self
        self.compmgr.all_product_envs = lambda: [self.compmgr, self.compmgr]

        class ComponentA(Component):
            implements(ITest)

        class ComponentB(Component):
            mp_extension_point = MultiProductExtensionPoint(ITest)

        components = ComponentB(self.compmgr).mp_extension_point
        self.assertEqual(len(components), 1)
        for c in components:
            self.assertIsInstance(c, ComponentA)


class ITest(Interface):
    def test():
        """Dummy function."""


def test_suite():
    return unittest.TestSuite([
        unittest.makeSuite(MultiProductExtensionPointTestCase, 'test'),
    ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
