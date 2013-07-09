import unittest
import tempfile
import shutil
from trac.test import EnvironmentStub, Mock, MockPerm
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
