# -*- coding: utf-8 -*-
#
# Copyright (C) 2007-2009 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.org/wiki/TracLicense.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://trac.edgewall.org/log/.

import doctest
import unittest

from trac import resource
from trac.resource import IResourceChangeListener
from trac.core import implements, Component


class ResourceTestCase(unittest.TestCase):

    def test_equals(self):
        # Plain equalities
        self.assertEqual(resource.Resource(), resource.Resource())
        self.assertEqual(resource.Resource(None), resource.Resource())
        self.assertEqual(resource.Resource('wiki'), resource.Resource('wiki'))
        self.assertEqual(resource.Resource('wiki', 'WikiStart'),
                         resource.Resource('wiki', 'WikiStart'))
        self.assertEqual(resource.Resource('wiki', 'WikiStart', 42),
                         resource.Resource('wiki', 'WikiStart', 42))
        # Inequalities
        self.assertNotEqual(resource.Resource('wiki', 'WikiStart', 42),
                            resource.Resource('wiki', 'WikiStart', 43))
        self.assertNotEqual(resource.Resource('wiki', 'WikiStart', 0),
                            resource.Resource('wiki', 'WikiStart', None))
        # Resource hierarchy
        r1 = resource.Resource('attachment', 'file.txt')
        r1.parent = resource.Resource('wiki', 'WikiStart')
        r2 = resource.Resource('attachment', 'file.txt')
        r2.parent = resource.Resource('wiki', 'WikiStart')
        self.assertEqual(r1, r2)
        r2.parent = r2.parent(version=42)
        self.assertNotEqual(r1, r2)

class TestResourceChangeListener(Component):
    implements(IResourceChangeListener)

    def __init__(self):
        self.resource_type = None

    def callback(self, action, resource, context, old_values = None):
        pass

    def match_resource(self, resource):
        if self.resource_type is None:
            return False
        return isinstance(resource, self.resource_type)

    def resource_created(self, resource, context = None):
        self.action = "created"
        self.resource = resource
        self.context = context
        self.callback(self.action, resource, context)

    def resource_changed(self, resource, old_values, context = None):
        self.action = "changed"
        self.resource = resource
        self.old_values = old_values
        self.context = context
        self.callback(
            self.action, resource, context, old_values=self.old_values)

    def resource_deleted(self, resource, context = None):
        self.action = "deleted"
        self.resource = resource
        self.context = context
        self.callback(self.action, resource, context)

    def resource_version_deleted(self, resource, context):
        self.action = "version_deleted"
        self.resource = resource
        self.context = context
        self.callback(self.action, resource, context)

def suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(resource))
    suite.addTest(unittest.makeSuite(ResourceTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
