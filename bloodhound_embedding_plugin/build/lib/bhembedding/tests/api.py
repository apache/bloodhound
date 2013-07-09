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
