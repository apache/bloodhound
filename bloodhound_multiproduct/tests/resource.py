# -*- coding: utf-8 -*-
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

from datetime import datetime
import os.path
import shutil
from StringIO import StringIO
import tempfile
import unittest

from trac.attachment import Attachment
from trac import resource 
import trac.ticket.report       # report resources ?
import trac.ticket.roadmap      # milestone resources
import trac.ticket.api          # ticket resources
from trac.ticket.model import Ticket
from trac.ticket.tests.api import TicketSystemTestCase 
from trac.util.datefmt import utc
import trac.wiki.api            # wiki resources
from trac.wiki.model import WikiPage

from multiproduct.api import MultiProductSystem
from multiproduct.env import ProductEnvironment
from tests.env import MultiproductTestCase

class ProductResourceTestCase(MultiproductTestCase):
    def setUp(self):
        self._mp_setup()
        self.global_env = self.env
        self._load_product_from_data(self.global_env, u'xü')

        self.env = ProductEnvironment(self.global_env, self.default_product)
        self.env1 = ProductEnvironment(self.global_env, u'xü')

        self._load_default_data(self.global_env)
        self._load_default_data(self.env1)

        # Enable product system component in product context
        self.env.enable_component(MultiProductSystem)

    def tearDown(self):
        self.global_env.reset_db()
        self.global_env = self.env = None


class ProductAttachmentResourceTestCase(ProductResourceTestCase):
    def setUp(self):
        ProductResourceTestCase.setUp(self)
        self.global_env.path = os.path.join(tempfile.gettempdir(),
                                            'trac-tempenv')
        if os.path.exists(self.global_env.path):
            shutil.rmtree(self.global_env.path)
        os.mkdir(self.global_env.path)

        attachment = Attachment(self.global_env, 'ticket', 1)
        attachment.description = 'Global Bar'
        attachment.insert('foo.txt', StringIO(''), 0)

        attachment = Attachment(self.env1, 'ticket', 1)
        attachment.description = 'Product Bar'
        attachment.insert('foo.txt', StringIO(''), 0)
        self.resource = resource.Resource('ticket', 
                                          1).child('attachment', 'foo.txt')

    def tearDown(self):
        shutil.rmtree(self.global_env.path)
        ProductResourceTestCase.tearDown(self)

    def test_global_neighborhood_attachments(self):
        target = resource.Neighborhood('global', None).child(self.resource)

        self.assertEquals("[global:] Attachment 'foo.txt' in [global:] Ticket #1", 
                          resource.get_resource_description(self.env, target))
        self.assertEquals("[global:] Attachment 'foo.txt' in [global:] Ticket #1", 
                          resource.get_resource_name(self.env, target))
        self.assertEquals("[global:] foo.txt ([global:] Ticket #1)", 
                          resource.get_resource_shortname(self.env, target))
        self.assertEquals('Global Bar', 
                          resource.get_resource_summary(self.env, target))
        self.assertEquals('http://example.org/trac.cgi/attachment/ticket/1/foo.txt', 
                          resource.get_resource_url(self.env, 
                                                    target, self.env.href))

    def test_product_neighborhood_attachments(self):
        target = resource.Neighborhood('product', u'xü').child(self.resource)

        self.assertEquals(u"[product:xü] Attachment 'foo.txt' in [product:xü] Ticket #1", 
                          resource.get_resource_description(self.env, target))
        self.assertEquals(u"[product:xü] Attachment 'foo.txt' in [product:xü] Ticket #1", 
                          resource.get_resource_name(self.env, target))
        self.assertEquals(u"[product:xü] foo.txt ([product:xü] Ticket #1)", 
                          resource.get_resource_shortname(self.env, target))
        self.assertEquals('Product Bar', 
                          resource.get_resource_summary(self.env, target))
        self.assertEquals('http://example.org/trac.cgi/products/x%C3%BC/attachment/ticket/1/foo.txt', 
                          resource.get_resource_url(self.env, 
                                                    target, self.env.href))


class ProductMilestoneResourceTestCase(ProductResourceTestCase):
    resource = resource.Resource('milestone', 'milestone1')

    def test_global_neighborhood_milestone(self):
        target = resource.Neighborhood('global', None).child(self.resource)

        self.assertEquals("[global:] Milestone milestone1", 
                          resource.get_resource_description(self.env, target))
        self.assertEquals("[global:] Milestone milestone1", 
                          resource.get_resource_name(self.env, target))
        self.assertEquals("milestone1", 
                          resource.get_resource_shortname(self.env, target))
        self.assertEquals("[global:] Milestone milestone1", 
                          resource.get_resource_summary(self.env, target))
        self.assertEquals('http://example.org/trac.cgi/milestone/milestone1', 
                          resource.get_resource_url(self.env, 
                                                    target, self.env.href))

    def test_product_neighborhood_milestone(self):
        target = resource.Neighborhood('product', u'xü').child(self.resource)

        self.assertEquals(u"[product:xü] Milestone milestone1", 
                          resource.get_resource_description(self.env, target))
        self.assertEquals(u"[product:xü] Milestone milestone1", 
                          resource.get_resource_name(self.env, target))
        self.assertEquals(u"milestone1", 
                          resource.get_resource_shortname(self.env, target))
        self.assertEquals(u"[product:xü] Milestone milestone1", 
                          resource.get_resource_summary(self.env, target))
        self.assertEquals('http://example.org/trac.cgi/products/x%C3%BC/milestone/milestone1', 
                          resource.get_resource_url(self.env, 
                                                    target, self.env.href))


# FIXME: No resource manager for reports in core ?
class ProductReportResourceTestCase(ProductResourceTestCase):
    resource = resource.Resource('report', 1)

    def test_global_neighborhood_report(self):
        target = resource.Neighborhood('global', None).child(self.resource)

        self.assertEquals("[global:] report:1", 
                          resource.get_resource_description(self.env, target))
        self.assertEquals("[global:] report:1", 
                          resource.get_resource_name(self.env, target))
        self.assertEquals("[global:] report:1", 
                          resource.get_resource_shortname(self.env, target))
        self.assertEquals('[global:] report:1 at version None', 
                          resource.get_resource_summary(self.env, target))
        self.assertEquals('http://example.org/trac.cgi/report/1', 
                          resource.get_resource_url(self.env, 
                                                    target, self.env.href))

    def test_product_neighborhood_report(self):
        target = resource.Neighborhood('product', u'xü').child(self.resource)

        self.assertEquals(u"[product:xü] report:1", 
                          resource.get_resource_description(self.env, target))
        self.assertEquals(u"[product:xü] report:1", 
                          resource.get_resource_name(self.env, target))
        self.assertEquals(u"[product:xü] report:1", 
                          resource.get_resource_shortname(self.env, target))
        self.assertEquals(u"[product:xü] report:1 at version None", 
                          resource.get_resource_summary(self.env, target))
        self.assertEquals('http://example.org/trac.cgi/products/x%C3%BC/report/1', 
                          resource.get_resource_url(self.env, 
                                                    target, self.env.href))


class ProductTicketResourceTestCase(ProductResourceTestCase):
    def _new_ticket(self, env, ticket_dict):
        ticket = Ticket(env)
        ticket.populate(ticket_dict)
        return ticket.insert()

    def setUp(self):
        ProductResourceTestCase.setUp(self)

    def test_global_neighborhood_ticket(self):
        nbh = resource.Neighborhood('global', None)
        data = dict(summary='Ticket summary', description='Ticket description',
                    type='enhancement', status='new')
        target = nbh.child('ticket', self._new_ticket(self.global_env, data))

        self.assertEquals("[global:] Ticket #1", 
                          resource.get_resource_description(self.env, target))
        self.assertEquals("[global:] Ticket #1", 
                          resource.get_resource_name(self.env, target))
        self.assertEquals("[global:] #1", 
                          resource.get_resource_shortname(self.env, target))
        self.assertEquals('enhancement: Ticket summary (new)', 
                          resource.get_resource_summary(self.env, target))
        self.assertEquals('http://example.org/trac.cgi/ticket/1', 
                          resource.get_resource_url(self.env, 
                                                    target, self.env.href))

    def test_product_neighborhood_ticket(self):
        nbh = resource.Neighborhood('product', u'xü')
        data = dict(summary='Ticket summary', description='Ticket description',
                    type='task', status='accepted')
        target = nbh.child('ticket', self._new_ticket(self.env1, data))

        self.assertEquals(u"[product:xü] Ticket #1", 
                          resource.get_resource_description(self.env, target))
        self.assertEquals(u"[product:xü] Ticket #1", 
                          resource.get_resource_name(self.env, target))
        self.assertEquals(u"[product:xü] #1", 
                          resource.get_resource_shortname(self.env, target))
        self.assertEquals(u"task: Ticket summary (accepted)", 
                          resource.get_resource_summary(self.env, target))
        self.assertEquals('http://example.org/trac.cgi/products/x%C3%BC/ticket/1', 
                          resource.get_resource_url(self.env, 
                                                    target, self.env.href))


#class ProductVcsResourceTestCase(ProductResourceTestCase):
#    def setUp(self):
#        pass
#
#    def tearDown(self):
#        pass
#
#    def test_global_neighborhood_versioncontrol(self):
#        raise NotImplementedError()
#
#    def test_product_neighborhood_versioncontrol(self):
#        raise NotImplementedError()


class ProductWikiResourceTestCase(ProductResourceTestCase):
    resource = resource.Resource('wiki', 'TestPage', version=2)

    def setUp(self):
        ProductResourceTestCase.setUp(self)

        page = WikiPage(self.global_env)
        page.name = 'TestPage'
        page.text = 'Bla bla'
        t = datetime(2001, 1, 1, 1, 1, 1, 0, utc)
        page.save('joe', 'Testing global', '::1', t)
        page.text = 'Bla bla bla'
        t = datetime(2002, 2, 2, 2, 2, 2, 0, utc)
        page.save('joe', 'Testing global 2', '::1', t)

        page = WikiPage(self.env1)
        page.name = 'TestPage'
        page.text = 'alb alB'
        t = datetime(2011, 1, 1, 1, 1, 1, 0, utc)
        page.save('mary', 'Testing product', '::1', t)
        page.text = 'Bla bla bla'
        t = datetime(2012, 2, 2, 2, 2, 2, 0, utc)
        page.save('mary', 'Testing product 2', '::1', t)

    def test_global_neighborhood_wiki(self):
        target = resource.Neighborhood('global', None).child(self.resource)

        self.assertEquals("TestPage", 
                          resource.get_resource_description(self.env, target))
        self.assertEquals("TestPage", 
                          resource.get_resource_name(self.env, target))
        self.assertEquals("TestPage", 
                          resource.get_resource_shortname(self.env, target))
        self.assertEquals("TestPage", 
                          resource.get_resource_summary(self.env, target))
        self.assertEquals('http://example.org/trac.cgi/wiki/TestPage?version=2', 
                          resource.get_resource_url(self.env, 
                                                    target, self.env.href))

    def test_product_neighborhood_wiki(self):
        target = resource.Neighborhood('product', u'xü').child(self.resource)

        self.assertEquals(u"TestPage", 
                          resource.get_resource_description(self.env, target))
        self.assertEquals(u"TestPage", 
                          resource.get_resource_name(self.env, target))
        self.assertEquals(u"TestPage", 
                          resource.get_resource_shortname(self.env, target))
        self.assertEquals(u"TestPage", 
                          resource.get_resource_summary(self.env, target))
        self.assertEquals('http://example.org/trac.cgi/products/x%C3%BC/wiki/TestPage?version=2', 
                          resource.get_resource_url(self.env, 
                                                    target, self.env.href))


def test_suite():
    return unittest.TestSuite([
        unittest.makeSuite(ProductAttachmentResourceTestCase, 'test'),
        unittest.makeSuite(ProductMilestoneResourceTestCase, 'test'),
        unittest.makeSuite(ProductReportResourceTestCase, 'test'),
        unittest.makeSuite(ProductTicketResourceTestCase, 'test'),
#        unittest.makeSuite(ProductVcsResourceTestCase, 'test'),
        unittest.makeSuite(ProductWikiResourceTestCase, 'test'),
    ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
