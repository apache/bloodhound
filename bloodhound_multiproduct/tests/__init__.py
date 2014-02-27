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

import logging
import sys
from collections import deque
from fnmatch import fnmatch
if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from pkg_resources import resource_exists, resource_filename, \
                          resource_isdir, resource_listdir


class TestLoader(unittest.TestLoader):
    testLoaderAttribute = '__testloader__'
    testMethodPrefix = 'test'
    sortTestMethodsUsing = cmp
    suiteClass = unittest.TestSuite

    def discover_package(self, package_or_requirement, pattern='*/test*.py',
                         ignore_subpkg_root=True, exclude=None):
        """Find and return all test modules from the specified package
        directory, recursing into subdirectories to find them. Only test files
        that match the pattern will be loaded. (Using shell style pattern
        matching.)

        All test modules must be importable from the top level of the project
        and registered with `pkg_resources` (e.g. via `setup.py develop`).

        If a target test module contains a '__testloader__' attribute then
        related object will override current loader for every individual
        module across the hierarchy.
        """
        pending = deque([(package_or_requirement, self, True)])
        tests = []
        log = logging.getLogger('bh.tests')
        if len(log.handlers) == 0:
            # Configure logger instance. otherwise messages won't be displayed
            _configure_logger(log)
        while pending:
            mdlnm, loader, isdir = pending.popleft()
            try:
                mdl = self._get_module_from_name(mdlnm)
            except (ImportError, ValueError):
                # Log import error and skip packages that don't import
                log.exception('Discovered package %s but import failed',
                              mdlnm)
                continue
            loader = getattr(mdl, self.testLoaderAttribute, None) or loader
            if not (isdir and ignore_subpkg_root):
                if mdlnm != package_or_requirement and hasattr(mdl, 'test_suite'):
                    tests.append(mdl.test_suite())
                else:
                    tests.append(loader.loadTestsFromModule(mdl))
            if isdir and resource_exists(mdlnm, '__init__.py'):
                for fnm in resource_listdir(mdlnm, ''):
                    fpath = resource_filename(mdlnm, fnm)
                    if resource_isdir(mdlnm, fnm) \
                            and (exclude is None
                                 or not fnmatch(fpath + '/', exclude)):
                        pending.append((mdlnm + '.' + fnm, loader, True))
                    elif any(fnm.endswith(ext) for ext in ['.py', '.pyc']) \
                            and fnmatch(fpath, pattern) \
                            and fnm != '__init__.py'\
                            and (exclude is None
                                 or not fnmatch(fpath, exclude)):
                        submdlnm = mdlnm + '.' + fnm.rsplit('.', 1)[0]
                        pending.append((submdlnm, loader, False))
        return self.suiteClass(tests)

    def _get_module_from_name(self, name):
        __import__(name)
        return sys.modules[name]


def _configure_logger(log):
    # See logging.basicConfig
    handler = logging.StreamHandler()
    formatter = logging.Formatter(logging.BASIC_FORMAT, None)
    handler.setFormatter(formatter)
    log.addHandler(handler)


def test_suite():
    return TestLoader().discover_package('tests', pattern='*.py',
                                         exclude='*/functional/*')

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
