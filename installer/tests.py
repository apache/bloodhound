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

"""Tests for bloodhound_setup.py"""

import unittest
import shutil
import os
from tempfile import mkdtemp, NamedTemporaryFile
from bloodhound_setup import backupfile, BloodhoundSetup
from functools import partial

class BackupfileTest(unittest.TestCase):
    """Unit tests for backupfile routine"""
    def setUp(self):
        self.tempdir = mkdtemp()
        self.original = NamedTemporaryFile(dir=self.tempdir)

    def tearDown(self):
        self.original.close()
        shutil.rmtree(self.tempdir)

    def test_backup_creates_new_file(self):
        """Checks that a new file is created"""
        orig = self.original.name
        new = backupfile(orig)
        self.assertNotEqual(orig, new)
        self.assert_(os.path.exists(orig))
        self.assert_(os.path.exists(new))

    def test_multiple_backup_creates_new_files(self):
        """Checks that, for a small finite number of backups, multiple
        backups do not overwrite old backups. The limit is effectively 65"""
        orig = self.original.name
        backups = [backupfile(orig) for i in range(65)]
        unique_set = set([orig, ] + backups)
        self.assertEqual(len(unique_set), 66)

class BloodhoundSetupTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = mkdtemp()
        self.bhs = BloodhoundSetup({})
        self.basedata =  {'section': {'option1': 'option1value',
                              'option2': 'option2value',},}
    
    def tearDown(self):
        shutil.rmtree(self.tempdir)
    
    def test_db_str_no_options(self):
        """Checks that giving no options at all has defaults enough to create
        a sqlite db string"""
        self.assertEqual(self.bhs._generate_db_str({}), 'sqlite:' +
                         os.path.join('db', 'bloodhound.db'))
    
    def test_db_str_provided_db_string(self):
        """Checks that if a dbstring is provided it will not be respected above
        other options"""
        dbstr = 'sillyexample'
        options = {'dbstring': dbstr,}
        self.assertEqual(self.bhs._generate_db_str(options), dbstr)
    
    def test_writeconfig_create_basic_config(self):
        filepath = os.path.join(self.tempdir, 'basic.ini')
        data =  [self.basedata]
        self.bhs.writeconfig(filepath, data)
        self.assert_(os.path.exists(filepath))
        #check the file
        with file(filepath) as f:
            fdata = f.read()
            self.assertIn('option1value', fdata)
    
    def test_writeconfig_update_config(self):
        """Checks that writing a new config with non-overlapping values updates
        an existing file"""
        filepath = os.path.join(self.tempdir, 'basic.ini')
        data =  [self.basedata]
        self.bhs.writeconfig(filepath, data)
        newdata = [{'section': {'option3': 'option3value',},}]
        self.bhs.writeconfig(filepath, newdata)
        #check the file
        with file(filepath) as f:
            fdata = f.read()
            self.assertIn('option3value', fdata)
    
    def test_writeconfig_update_config_overwrite_values(self):
        """Checks that writing a new config with non-overlapping values updates
        an existing file"""
        filepath = os.path.join(self.tempdir, 'basic.ini')
        data =  [self.basedata]
        self.bhs.writeconfig(filepath, data)
        newdata = [{'section': {'option2': 'newopt2value',},}]
        self.bhs.writeconfig(filepath, newdata)
        with file(filepath) as f:
            fdata = f.read()
            self.assertIn('newopt2value', fdata)
            self.assertNotIn('option2value', fdata)

if __name__ == '__main__':
    unittest.main()
