
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

"""Configuration objects for Bloodhound product environments"""

__all__ = 'Configuration', 'Section'

import os.path

from trac.config import Configuration, ConfigurationError, Option, \
        OrderedExtensionsOption, Section, _use_default
from trac.resource import ResourceNotFound
from trac.util.text import to_unicode

from multiproduct.model import ProductSetting
from multiproduct.perm import MultiproductPermissionPolicy

class Configuration(Configuration):
    """Product-aware settings repository equivalent to instances of
    `trac.config.Configuration` (and thus `ConfigParser` from the
    Python Standard Library) but retrieving configuration values 
    from the database.
    """
    def __init__(self, env, product, parents=None):
        """Initialize configuration object with an instance of 
        `trac.env.Environment` and product prefix.

        Optionally it is possible to inherit settings from parent
        Configuration objects. Environment's configuration will not
        be added to parents list.
        """
        self.env = env
        self.product = to_unicode(product)
        self._sections = {}
        self._setup_parents(parents)

    def __getitem__(self, name):
        """Return the configuration section with the specified name.
        """
        if name not in self._sections:
            self._sections[name] = Section(self, name)
        return self._sections[name]

    def sections(self, compmgr=None, defaults=True):
        """Return a list of section names.

        If `compmgr` is specified, only the section names corresponding to
        options declared in components that are enabled in the given
        `ComponentManager` are returned.
        """
        sections = set(to_unicode(s) \
                for s in ProductSetting.get_sections(self.env, self.product))
        for parent in self.parents:
            sections.update(parent.sections(compmgr, defaults=False))
        if defaults:
            sections.update(self.defaults(compmgr))
        return sorted(sections)

    def has_option(self, section, option, defaults=True):
        """Returns True if option exists in section in either the project
        trac.ini or one of the parents, or is available through the Option
        registry.

        (since Trac 0.11)
        """
        if ProductSetting.exists(self.env, self.product, section, option):
            return True
        for parent in self.parents:
            if parent.has_option(section, option, defaults=False):
                return True
        return defaults and (section, option) in Option.registry

    def save(self):
        """Nothing to do.

        Notice: Opposite to Trac's Configuration objects Bloodhound's
        product configuration objects commit changes to the database 
        immediately. Thus there's no much to do in this method.
        """

    def parse_if_needed(self, force=False):
        """Just invalidate options cache.

        Notice: Opposite to Trac's Configuration objects Bloodhound's
        product configuration objects commit changes to the database 
        immediately. Thus there's no much to do in this method.
        """
        for section in self.sections():
            self[section]._cache.clear()

    def touch(self):
        pass

    def set_defaults(self, compmgr=None):
        """Retrieve all default values and store them explicitly in the
        configuration, so that they can be saved to file.

        Values already set in the configuration are not overridden.
        """
        for section, default_options in self.defaults(compmgr).items():
            for name, value in default_options.items():
                if not ProductSetting.exists(self.env, self.product,
                        section, name):
                    if any(parent[section].contains(name, defaults=False)
                           for parent in self.parents):
                        value = None
                    self.set(section, name, value)

    # Helper methods

    def _setup_parents(self, parents=None):
        """Inherit configuration from parent `Configuration` instances.
        If there's a value set to 'file' option in 'inherit' section then
        it will be considered as a list of paths to .ini files
        that will be added to parents list as well.
        """
        from trac import config
        self.parents = (parents or [])
        for filename in self.get('inherit', 'file').split(','):
            filename = Section._normalize_path(filename.strip(), self.env)
            self.parents.append(config.Configuration(filename))

class Section(Section):
    """Proxy for a specific configuration section.

    Objects of this class should not be instantiated directly.
    """
    __slots__ = ['config', 'name', 'overridden', '_cache']

    @staticmethod
    def optionxform(optionstr):
        return to_unicode(optionstr.lower());

    def __init__(self, config, name):
        self.config = config
        self.name = to_unicode(name)
        self.overridden = {}
        self._cache = {}

    @property
    def env(self):
        return self.config.env

    @property
    def product(self):
        return self.config.product

    def contains(self, key, defaults=True):
        key = self.optionxform(key)
        if ProductSetting.exists(self.env, self.product, self.name, key):
            return True
        for parent in self.config.parents:
            if parent[self.name].contains(key, defaults=False):
                return True
        return defaults and Option.registry.has_key((self.name, key))

    __contains__ = contains

    def iterate(self, compmgr=None, defaults=True):
        """Iterate over the options in this section.

        If `compmgr` is specified, only return default option values for
        components that are enabled in the given `ComponentManager`.
        """
        options = set()
        name_str = self.name
        for setting in ProductSetting.select(self.env,
                where={'product':self.product, 'section':name_str}):
            option = self.optionxform(setting.option)
            options.add(option)
            yield option
        for parent in self.config.parents:
            for option in parent[self.name].iterate(defaults=False):
                loption = self.optionxform(option)
                if loption not in options:
                    options.add(loption)
                    yield option
        if defaults:
            for section, option in Option.get_registry(compmgr).keys():
                if section == self.name and \
                        self.optionxform(option) not in options:
                    yield option

    __iter__ = iterate

    def __repr__(self):
        return '<%s [%s , %s]>' % (self.__class__.__name__, \
                self.product, self.name)

    def get(self, key, default=''):
        """Return the value of the specified option.

        Valid default input is a string. Returns a string.
        """
        key = self.optionxform(key)
        cached = self._cache.get(key, _use_default)
        if cached is not _use_default:
            return cached
        name_str = self.name
        key_str = to_unicode(key)
        settings = ProductSetting.select(self.env, 
                where={'product':self.product, 'section':name_str,
                        'option':key_str})
        if len(settings) > 0:
            value = settings[0].value
        else:
            for parent in self.config.parents:
                value = parent[self.name].get(key, _use_default)
                if value is not _use_default:
                    break
            else:
                if default is not _use_default:
                    option = Option.registry.get((self.name, key))
                    value = option.default if option else _use_default
                else:
                    value = _use_default
        if value is _use_default:
            return default
        if not value:
            value = u''
        elif isinstance(value, basestring):
            value = to_unicode(value)
        self._cache[key] = value
        return value

    def getpath(self, key, default=''):
        """Return a configuration value as an absolute path.

        Relative paths are resolved relative to `conf` subfolder 
        of the target global environment. This approach is consistent
        with TracIni path resolution.

        Valid default input is a string. Returns a normalized path.

        (enabled since Trac 0.11.5)
        """
        path = self.get(key, default)
        if not path:
            return default
        return self._normalize_path(path, self.env)

    def remove(self, key):
        """Delete a key from this section.

        Like for `set()`, the changes won't persist until `save()` gets called.
        """
        key_str = self.optionxform(key)
        option_key = {
                'product' : self.product, 
                'section' : self.name,
                'option' : key_str,
            }
        try:
            setting = ProductSetting(self.env, keys=option_key)
        except ResourceNotFound:
            self.env.log.warning("No record for product option %s", option_key)
        else:
            self._cache.pop(key, None)
            setting.delete()
            self.env.log.info("Removing product option %s", option_key)

    def set(self, key, value):
        """Change a configuration value.

        These changes will be persistent right away.
        """
        key_str = self.optionxform(key)
        value_str = to_unicode(value)
        self._cache.pop(key_str, None)
        option_key = {
                'product' : self.product, 
                'section' : self.name,
                'option' : key_str,
            }
        try:
            setting = ProductSetting(self.env, option_key)
        except ResourceNotFound:
            if value is not None:
                # Insert new record in the database
                setting = ProductSetting(self.env)
                setting._data.update(option_key)
                setting._data['value'] = value_str
                self.env.log.debug('Writing option %s', setting._data)
                setting.insert()
        else:
            if value is None:
                # Delete existing record from the database
                # FIXME : Why bother with setting overriden
                self.overridden[key] = True
                setting.delete()
            else:
                # Update existing record
                setting._data['value'] = value
                setting.update()

    # Helper methods

    @staticmethod
    def _normalize_path(path, env):
        if not os.path.isabs(path):
            path = os.path.join(env.path, 'conf', path)
        return os.path.normcase(os.path.realpath(path))

#--------------------
# Option override classes
#--------------------

class ProductPermissionPolicyOption(OrderedExtensionsOption):
    """Prepend an instance of `multiproduct.perm.MultiproductPermissionPolicy`
    """
    def __get__(self, instance, owner):
        # FIXME: Better handling of recursive imports
        from multiproduct.env import ProductEnvironment

        if instance is None:
            return self
        components = OrderedExtensionsOption.__get__(self, instance, owner)
        env = getattr(instance, 'env', None)
        return [MultiproductPermissionPolicy(env)] + components \
               if isinstance(env, ProductEnvironment) \
               else components
