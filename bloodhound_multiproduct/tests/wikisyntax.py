
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

"""Tests for Apache(TM) Bloodhound's core wiki syntax in product environments"""

import os.path
import re
import shutil
import tempfile
import unittest

from trac.attachment import Attachment
from trac.tests import wikisyntax

from multiproduct.env import ProductEnvironment
from tests.env import MultiproductTestCase
from tests.wiki import formatter

def attachment_setup(tc):
    import trac.ticket.api
    import trac.wiki.api
    tc.global_env.path = os.path.join(tempfile.gettempdir(), 'trac-tempenv')
    del tc.env.path
    attachment = Attachment(tc.env, 'wiki', 'WikiStart')
    attachment.insert('file.txt', tempfile.TemporaryFile(), 0)
    attachment = Attachment(tc.env, 'ticket', 123)
    attachment.insert('file.txt', tempfile.TemporaryFile(), 0)
    attachment = Attachment(tc.env, 'wiki', 'SomePage/SubPage')
    attachment.insert('foo.txt', tempfile.TemporaryFile(), 0)

def attachment_teardown(tc):
    shutil.rmtree(tc.global_env.path)
    tc.global_env.reset_db()


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(formatter.test_suite(wikisyntax.SEARCH_TEST_CASES, 
                                  file=wikisyntax.__file__))
    suite.addTest(formatter.test_suite(wikisyntax.ATTACHMENT_TEST_CASES, 
                                  file=wikisyntax.__file__,
                                  context=('wiki', 'WikiStart'),
                                  setup=attachment_setup,
                                  teardown=attachment_teardown))
    suite.addTest(formatter.test_suite(wikisyntax.EMAIL_TEST_CASE_DEFAULT, 
                                  file=wikisyntax.__file__,
                                  context=wikisyntax.email_default_context()))
    suite.addTest(formatter.test_suite(wikisyntax.EMAIL_TEST_CASE_NEVER_OBFUSCATE,
                                  file=wikisyntax.__file__,
                                  context=wikisyntax.email_default_context(),
                                  setup=wikisyntax.email_never_obfuscate_setup))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

