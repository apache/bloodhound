# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2013 Jun Omae <jun66j5@gmail.com>
# Copyright (C) 2012-2013 Ryan J Ollos <ryan.j.ollos@gmail.com>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.

import unittest

from trac.test import Mock, MockPerm, EnvironmentStub
from trac.core import TracError
from trac.core import implements, Component
from bhembedding.api import EmbeddingSystem


class EmbeddingSystemTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        self.embedding_system = EmbeddingSystem(self.env)
        self.req = Mock()

    def tearDown(self):
        self.env.reset_db()
