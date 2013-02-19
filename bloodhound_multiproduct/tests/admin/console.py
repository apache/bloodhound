
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

"""Tests for Apache(TM) Bloodhound's admin console in product environments"""

import os.path
import sys
from StringIO import StringIO
import unittest

from trac.admin.tests.console import load_expected_results, \
        STRIP_TRAILING_SPACE, TracadminTestCase

from multiproduct.env import ProductEnvironment
from tests.env import MultiproductTestCase

class ProductTracadminTestCase(TracadminTestCase, MultiproductTestCase):

    expected_results = load_expected_results(
            os.path.join(os.path.split(__file__)[0], 'console-tests.txt'),
            '===== (test_[^ ]+) =====')

    @property
    def env(self):
        env = getattr(self, '_env', None)
        if env is None:
            self.global_env = self._setup_test_env(
                    enable=('trac.*', 'multiproduct.*'), 
                    disable=('trac.tests.*',),
                )
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
        self.global_env = self._env = None

    def _execute(self, cmd, strip_trailing_space=True, input=None):
        _in = sys.stdin
        _err = sys.stderr
        _out = sys.stdout
        try:
            if input:
                sys.stdin = StringIO(input.encode('utf-8'))
                sys.stdin.encoding = 'utf-8' # fake input encoding
            sys.stderr = sys.stdout = out = StringIO()
            out.encoding = 'utf-8' # fake output encoding
            retval = None
            try:
                retval = self._admin.onecmd(cmd)
            except SystemExit:
                pass
            value = out.getvalue()
            if isinstance(value, str): # reverse what print_listing did
                value = value.decode('utf-8')
            if retval != 0:
                self.env.log.debug('trac-admin failure: %s', value)
            if strip_trailing_space:
                return retval, STRIP_TRAILING_SPACE.sub('', value)
            else:
                return retval, value
        finally:
            sys.stdin = _in
            sys.stderr = _err
            sys.stdout = _out


def test_suite():
    return unittest.TestSuite([
            unittest.makeSuite(ProductTracadminTestCase,'test'),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

