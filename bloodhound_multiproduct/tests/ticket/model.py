
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

"""Tests for Apache(TM) Bloodhound's tickets model in product environments"""

from datetime import datetime
import shutil
import unittest

from trac.ticket.model import Milestone
from trac.ticket.tests.model import TicketTestCase, TicketCommentTestCase, \
        TicketCommentEditTestCase, TicketCommentDeleteTestCase, EnumTestCase, \
        MilestoneTestCase, ComponentTestCase, VersionTestCase
from trac.util.datefmt import to_utimestamp, utc

from multiproduct.env import ProductEnvironment
from tests.env import MultiproductTestCase

class ProductTicketTestCase(TicketTestCase, MultiproductTestCase):

    def setUp(self):
        self._mp_setup()
        self.global_env = self.env
        self.env = ProductEnvironment(self.global_env, self.default_product)
        self._load_default_data(self.env)

        self.env.config.set('ticket-custom', 'foo', 'text')
        self.env.config.set('ticket-custom', 'cbon', 'checkbox')
        self.env.config.set('ticket-custom', 'cboff', 'checkbox')

    def tearDown(self):
        self.global_env.reset_db()
        self.env = self.global_env = None

class ProductTicketCommentTestCase(MultiproductTestCase):

    @property
    def env(self):
        env = getattr(self, '_env', None)
        if env is None:
            self.global_env = self._setup_test_env()
            self._upgrade_mp(self.global_env)
            self._setup_test_log(self.global_env)
            self._load_product_from_data(self.global_env, self.default_product)
            self._env = env = ProductEnvironment(
                    self.global_env, self.default_product)
            self._load_default_data(env)
        return env

    @env.setter
    def env(self, value):
        pass

    def tearDown(self):
        self.global_env.reset_db()
        self._env = self.global_env = None

class ProductTicketCommentEditTestCase(TicketCommentEditTestCase,
        ProductTicketCommentTestCase):
    pass

class ProductTicketCommentDeleteTestCase(TicketCommentDeleteTestCase,
        ProductTicketCommentTestCase):
    pass

class ProductEnumTestCase(EnumTestCase, MultiproductTestCase):
    def setUp(self):
        self._mp_setup()
        self.global_env = self.env
        self.env = ProductEnvironment(self.global_env, self.default_product)
        self._load_default_data(self.env)

    def tearDown(self):
        self.global_env.reset_db()
        self.env = self.global_env = None

class ProductMilestoneTestCase(MilestoneTestCase, MultiproductTestCase):
    def setUp(self):
        self.global_env = self._setup_test_env(create_folder=True)
        self._upgrade_mp(self.global_env)
        self._setup_test_log(self.global_env)
        self._load_product_from_data(self.global_env, self.default_product)

        self.env = ProductEnvironment(self.global_env, self.default_product)
        self._load_default_data(self.env)

    def tearDown(self):
        shutil.rmtree(self.global_env.path)
        self.global_env.reset_db()
        self.env = self.global_env = None

    def test_update_milestone(self):

        self.env.db_transaction("INSERT INTO milestone (name) VALUES ('Test')")

        milestone = Milestone(self.env, 'Test')
        t1 = datetime(2001, 01, 01, tzinfo=utc)
        t2 = datetime(2002, 02, 02, tzinfo=utc)
        milestone.due = t1
        milestone.completed = t2
        milestone.description = 'Foo bar'
        milestone.update()

        self.assertEqual(
            [('Test', to_utimestamp(t1), to_utimestamp(t2), 'Foo bar', 
                    self.default_product)],
            self.env.db_query("SELECT * FROM milestone WHERE name='Test'"))

class ProductComponentTestCase(ComponentTestCase, MultiproductTestCase):
    def setUp(self):
        self._mp_setup()
        self.global_env = self.env
        self.env = ProductEnvironment(self.global_env, self.default_product)
        self._load_default_data(self.env)

    def tearDown(self):
        self.global_env.reset_db()
        self.env = self.global_env = None

class ProductVersionTestCase(VersionTestCase, MultiproductTestCase):
    def setUp(self):
        self._mp_setup()
        self.global_env = self.env
        self.env = ProductEnvironment(self.global_env, self.default_product)
        self._load_default_data(self.env)

    def tearDown(self):
        self.global_env.reset_db()
        self.env = self.global_env = None


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ProductTicketTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ProductTicketCommentEditTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ProductTicketCommentDeleteTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ProductEnumTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ProductMilestoneTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ProductComponentTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ProductVersionTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

