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

"""Tests for Apache(TM) Bloodhound's product configuration objects"""

from ConfigParser import ConfigParser
from itertools import groupby
import os.path
import shutil
from StringIO import StringIO
import unittest

from trac.config import Option
from trac.tests.config import ConfigurationTestCase
from trac.util.text import to_unicode

from multiproduct.api import MultiProductSystem
from multiproduct.config import Configuration
from multiproduct.model import Product, ProductSetting
from tests.env import MultiproductTestCase

class ProductConfigTestCase(ConfigurationTestCase, MultiproductTestCase):
    r"""Test cases for Trac configuration objects rewritten for product 
    scope.
    """
    def setUp(self):
        r"""Replace Trac environment with product environment
        """
        self.env = self._setup_test_env()

        # Dummy config file, a sibling of trac.ini
        tmpdir = os.path.realpath(self.env.path)
        self.filename = os.path.join(tmpdir, 'conf', 'product.ini')
        # Ensure conf sub-folder is created
        os.mkdir(os.path.dirname(self.filename))

        self._upgrade_mp(self.env)
        self._setup_test_log(self.env)
        self._load_product_from_data(self.env, self.default_product)
        self._orig_registry = Option.registry
        Option.registry = {}

    def tearDown(self):
        Option.registry = self._orig_registry
        shutil.rmtree(self.env.path)
        self.env = None

    def _read(self, parents=None, product=None):
        r"""Override superclass method by returning product-aware configuration
        object retrieving settings from the database. Such objects will replace
        instances of `trac.config.Configuration` used in inherited test cases.
        """
        if product is None:
            product = self.default_product
        return Configuration(self.env, product, parents)

    def _write(self, lines, product=None):
        r"""Override superclass method by writing configuration values
        to the database rather than ini file in the filesystem.
        """
        if product is None:
            product = self.default_product
        product = to_unicode(product)
        fp = StringIO(('\n'.join(lines + [''])).encode('utf-8'))
        parser = ConfigParser()
        parser.readfp(fp, 'bh-product-test')
        with self.env.db_transaction as db:
            # Delete existing setting for target product , if any
            for setting in ProductSetting.select(self.env, db, 
                    {'product' : product}):
                setting.delete()
            # Insert new options
            for section in parser.sections():
                option_key = dict(
                        section=to_unicode(section), 
                        product=to_unicode(product)
                    )
                for option, value in parser.items(section):
                    option_key.update(dict(option=to_unicode(option)))
                    setting = ProductSetting(self.env)
                    setting._data.update(option_key)
                    setting._data['value'] = to_unicode(value)
                    setting.insert()

    def _test_with_inherit(self, testcb):
        """Almost exact copy of `trac.tests.config.ConfigurationTestCase`.
        Differences explained in inline comments.
        """
        # Parent configuration file created in environment's conf sub-folder
        # PS: This modification would not be necessary if the corresponding
        #     statement in overriden method would be written the same way
        #     but the fact that both files have the same parent folder
        #     is not made obvious in there
        sitename = os.path.join(os.path.dirname(self.filename), 'trac-site.ini')

        try:
            with open(sitename, 'w') as sitefile:
                sitefile.write('[a]\noption = x\n')

            self._write(['[inherit]', 'file = trac-site.ini'])
            testcb()
        finally:
            os.remove(sitename)

    def _dump_settings(self, config):
        product = config.product
        fields = ('section', 'option', 'value')
        rows = [tuple(getattr(s, f, None) for f in fields) for s in 
                ProductSetting.select(config.env, where={'product' : product})]

        dump = []
        for section, group in groupby(sorted(rows), lambda row: row[0]):
            dump.append('[%s]\n' % (section,))
            for row in group:
                dump.append('%s = %s\n' % (row[1], row[2]))
        return dump

    # Test cases rewritten to avoid reading config file. 
    # It does make sense for product config as it's stored in the database

    def test_set_and_save(self):
        config = self._read()
        config.set('b', u'öption0', 'y')
        config.set(u'aä', 'öption0', 'x')
        config.set('aä', 'option2', "Voilà l'été")  # UTF-8
        config.set(u'aä', 'option1', u"Voilà l'été") # unicode
        # Note: the following would depend on the locale.getpreferredencoding()
        # config.set('a', 'option3', "Voil\xe0 l'\xe9t\xe9") # latin-1
        self.assertEquals('x', config.get(u'aä', u'öption0'))
        self.assertEquals(u"Voilà l'été", config.get(u'aä', 'option1'))
        self.assertEquals(u"Voilà l'été", config.get(u'aä', 'option2'))
        config.save()

        dump = self._dump_settings(config)
        self.assertEquals([
                           u'[aä]\n',
                           u"option1 = Voilà l'été\n", 
                           u"option2 = Voilà l'été\n", 
                           u'öption0 = x\n', 
                           # u"option3 = VoilÃ  l'Ã©tÃ©\n", 
                           u'[b]\n',
                           u'öption0 = y\n', 
                           ],
                          dump)
        config2 = self._read()
        self.assertEquals('x', config2.get(u'aä', u'öption0'))
        self.assertEquals(u"Voilà l'été", config2.get(u'aä', 'option1'))
        self.assertEquals(u"Voilà l'été", config2.get(u'aä', 'option2'))
        # self.assertEquals(u"Voilà l'été", config2.get('a', 'option3'))

    def test_set_and_save_inherit(self):
        def testcb():
            config = self._read()
            config.set('a', 'option2', "Voilà l'été")  # UTF-8
            config.set('a', 'option1', u"Voilà l'été") # unicode
            self.assertEquals('x', config.get('a', 'option'))
            self.assertEquals(u"Voilà l'été", config.get('a', 'option1'))
            self.assertEquals(u"Voilà l'été", config.get('a', 'option2'))
            config.save()

            dump = self._dump_settings(config)
            self.assertEquals([
                               u'[a]\n',
                               u"option1 = Voilà l'été\n", 
                               u"option2 = Voilà l'été\n", 
                               u'[inherit]\n',
                               u"file = trac-site.ini\n", 
                               ],
                              dump)
            config2 = self._read()
            self.assertEquals('x', config2.get('a', 'option'))
            self.assertEquals(u"Voilà l'été", config2.get('a', 'option1'))
            self.assertEquals(u"Voilà l'été", config2.get('a', 'option2'))
        self._test_with_inherit(testcb)

    def test_overwrite(self):
        config = self._read()
        config.set('a', 'option', 'value1')
        self.assertEquals('value1', config.get('a', 'option'))
        config.set('a', 'option', 'value2')
        self.assertEquals('value2', config.get('a', 'option'))

def test_suite():
    return unittest.makeSuite(ProductConfigTestCase,'test')

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

