try:
    import unittest2 as unittest
except ImportError:
    import unittest

from bhsolr.tests import (
    backend
)


def suite():
    test_suite = unittest.TestSuite()
    return test_suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
else:
    test_suite = suite()
