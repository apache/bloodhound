
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

r"""Test artifacts.

The test suites have been run using Trac=0.11.1 , Trac=0.11.5 , Trac=0.11.7
"""

__metaclass__ = type

import sys

from trac.core import ComponentMeta
from trac.db.api import _parse_db_str, DatabaseManager
from trac.mimeview.api import Context
from trac.test import EnvironmentStub
from trac.util.compat import set

from bhdashboard.util import trac_version, trac_tags

#------------------------------------------------------
#    Trac environments used for testing purposes
#------------------------------------------------------

class EnvironmentStub(EnvironmentStub):
  r"""Enhanced stub of the trac.env.Environment object for testing.
  """

  # Dont break lazy evaluation. Otherwise RPC calls misteriously fail.
  @property
  def _abs_href(self):
    return self.abs_href

  def enable_component(self, clsdef):
    r"""Enable a plugin temporarily at testing time.
    """
    if trac_version < trac_tags[0]:
      # `enabled_components` should be enough in this case
      if clsdef not in self.enabled_components :
        self.enabled_components.append(clsdef)
    else:
      # Use environment configuration otherwise
      raise NotImplementedError("TODO: Enable components in Trac>=0.13")

  def disable_component(self, clsdef):
    r"""Disable a plugin temporarily at testing time.
    """
    if trac_version < trac_tags[0]:
      try:
        self.enabled_components.remove(clsdef)
      except ValueError :
        self.log.warning("Component %s was not enabled", clsdef)
    else:
      # Use environment configuration otherwise
      raise NotImplementedError("TODO: Disable components in Trac>=0.13")

  def rip_component(self, cls):
    r"""Disable a plugin forever and RIP it using the super-laser beam.
    """
    self.disable_component(cls)
    for reg in ComponentMeta._registry.itervalues():
      try:
        reg.remove(cls)
      except ValueError :
        pass

  if not hasattr(EnvironmentStub, 'reset_db'):

    # Copycat trac.test.EnvironmentStub.reset_db (Trac=0.11.5)
    def reset_db(self, default_data=None):
        r"""Remove all data from Trac tables, keeping the tables themselves.
        :param default_data: after clean-up, initialize with default data
        :return: True upon success
        """
        from trac import db_default

        db = self.get_db_cnx()
        db.rollback() # make sure there's no transaction in progress
        cursor = db.cursor()

        defdata = list(db_default.get_data(db))

        for table, cols, vals in defdata:
            cursor.execute("DELETE FROM %s" % (table,) )

        db.commit()

        if default_data:
            for table, cols, vals in defdata:
                cursor.executemany("INSERT INTO %s (%s) VALUES (%s)"
                                   % (table, ','.join(cols),
                                      ','.join(['%s' for c in cols])),
                                   vals)
        else:
            cursor.execute("INSERT INTO system (name, value) "
                           "VALUES (%s, %s)",
                           ('database_version', str(db_default.db_version)))
        db.commit()

#------------------------------------------------------
#    Minimalistic testing framework for Trac
#------------------------------------------------------

from dutest import DocTestLoader, DocTestSuiteFixture
from os.path import dirname
from types import MethodType

from bhdashboard.util import dummy_request

# Hide this module from tracebacks written into test results.
__unittest = True

class DocTestTracLoader(DocTestLoader):
  r"""A generic XUnit loader that allows to load doctests written 
  to check that Trac plugins behave as expected.
  """
  def set_env(self, env):
    if self.extraglobs is None :
      self.extraglobs = dict(env=env)
    else :
      self.extraglobs['env'] = env

  env = property(lambda self : self.extraglobs.get('env'), set_env, \
                  doc="""The Trac environment used in doctests.""")
  del set_env

  def __init__(self, dt_finder=None, globs=None, extraglobs=None, \
                          load=None, default_data=False, enable=None, \
                          disable=None, **opts):
    r"""Initialization. It basically works like `DocTestLoader`'s 
    initializer but creates also the Trac environment used for 
    testing purposes. The default behavior is to create an instance 
    of `EnvironmentStub` class. Subclasses can add more specific 
    keyword parameters in order to use them to create the 
    environment. Next it loads (and | or) enables the components 
    needed by the test suite.

    The following variables are magically available at testing time. 
    They can be used directly in doctests :

    - req         A dummy request object setup for anonymous access.
    - auth_req    A dummy request object setup like if user `murphy` was  
                  accessing the site.
    - env         the Trac environment used as a stub for testing 
                  purposes (i.e. `self.env`).

    @param dt_finder        see docs for `DocTestLoader.__init__` 
                            method.
    @param globs            see docs for `DocTestLoader.__init__` 
                            method.
    @param extraglobs       see docs for `DocTestLoader.__init__` 
                            method.
    @param load             a list of packages containing components 
                            that will be loaded to ensure they are 
                            available at testing time. It should be 
                            the top level module in that package 
                            (e.g. 'trac').
    @param default_data     If true, populate the database with some 
                            defaults. This parameter has to be 
                            handled by `createTracEnv` method.
    @param enable           a list of UNIX patterns specifying which 
                            components need to be enabled by default 
                            at testing time. This parameter should be 
                            handled by `createTracEnv` method.
    @param disable          a list of UNIX patterns specifying which 
                            components need to be disabled by default 
                            at testing time. Ignored in Trac<=0.11 .
                            This parameter should be 
                            handled by `createTracEnv` method.
    """
    super(DocTestTracLoader, self).__init__(dt_finder, globs, \
                                              extraglobs, **opts)
    if trac_version >= trac_tags[0]:
        opts['disable'] = disable
    self.env = self.createTracEnv(default_data, enable, **opts)
    self.load_components(load is None and self.default_packages or load)

  # Load trac built-in components by default
  default_packages = ['trac']

  def createTracEnv(self, default_data=False, enable=None, 
      disable=None, **params):
    r"""Create the Trac environment used for testing purposes. The 
    default behavior is to create an instance of `EnvironmentStub` 
    class. Subclasses can override this decision and add more specific 
    keyword parameters in order to control environment creation in 
    more detail. 

    All parameters supplied at initialization time. By default they 
    are ignored.
    @param default_data     If True, populate the database with some 
                            defaults.
    @param enable           a list of UNIX patterns specifying which 
                            components need to be enabled by default 
                            at testing time.
    @param disable          a list of UNIX patterns specifying which 
                            components need to be disabled by default 
                            at testing time. Ignored in Trac<0.13
    @return                 the environment used for testing purpose.
    """
    if trac_version >= trac_tags[0]:
      kwargs = {'disable' : disable}
    else :
      kwargs = {}
    return EnvironmentStub(default_data, enable, **kwargs)

  def load_components(self, pkgs):
    r"""Load some packages to ensure that the components they 
    implement are available at testing time.
    """
    from trac.loader import load_components
    for pkg in pkgs :
      try :
        __import__(pkg)
      except ImportError :
        pass                        # Skip pkg. What a shame !
      else :
        mdl = sys.modules[pkg]
        load_components(self.env, dirname(dirname(mdl.__file__)))

  class doctestSuiteClass(DocTestSuiteFixture):
    r"""Prepare the global namespace before running all doctests 
    in the suite. Reset the Trac environment.
    """
    username = 'murphy'

    @property
    def env(self):
      r"""The Trac environment involved in this test. It is 
      retrieved using the global namespace ;o).
      """
      return self.globalns['env']

    def new_request(self, uname=None, args=None):
      r"""Create and initialize a new request object.
      """
      req = dummy_request(self.env, uname)
      if args is not None :
        req.args = args
      return req

    def setUp(self):
      r"""Include two (i.e. `req` anonymous and `auth_req` 
      authenticated) request objects in the global namespace, before 
      running the doctests. Besides, clean up environment data and 
      include only default data.
      """
      from pprint import pprint
      from trac.core import ComponentMeta

      globs = self.globalns
      req = self.new_request(args=dict())
      auth_req = self.new_request(uname=self.username, args=dict())
      globs['req'] = req
      globs['auth_req'] = auth_req
      # TODO: If the source docstrings belong to a Trac component, 
      #       then instantiate it and include in the global 
      #       namespace.

      # Delete data in Trac tables
      from trac import db_default
      db = self.env.get_db_cnx()
      cursor = db.cursor()
      for table in db_default.schema:
        if trac_version < trac_tags[0]: # FIXME: Should it be (0, 12) ?
            cursor.execute("DELETE FROM " + table.name)
        else:
            cursor.execute("DROP TABLE " + table.name)
      db.commit()

      self.env.reset_db(default_data=True)

#------------------------------------------------------
#    Test artifacts used to test widget providers
#------------------------------------------------------

from bhdashboard.api import InvalidIdentifier

class DocTestWidgetLoader(DocTestTracLoader):
  r"""Load doctests used to test Trac RPC handlers.
  """
  class doctestSuiteClass(DocTestTracLoader.doctestSuiteClass):
    r"""Include the appropriate RPC handler in global namespace 
    before running all test cases in the suite.
    """

    def ns_from_name(self):
      r"""Extract the target namespace under test using the name
      of the DocTest instance manipulated by the suite.
      """
      try :
        return self._dt.name.split(':', 1)[0].split('|', 1)[-1]
      except :
        return None

    def partial_setup(self):
      r"""Perform partial setup due to some minor failure (e.g. 
      namespace missing in test name).
      """
      globs = self.globalns
      globs['widget'] = globs['ctx'] = globs['auth_ctx'] = None

    def setup_widget(self, widgetns):
      r"""(Insert | update) the IWidgetProvider in the global 
      namespace.

      @param widgetns             widget name.
      @throws RuntimeError        if a widget with requested name cannot 
                                  be found.
      """
      globs = self.globalns
      globs['ctx'] = Context.from_request(globs['req'])
      globs['auth_ctx'] = Context.from_request(globs['auth_req'])
      for wp in self.dbsys.providers :
        if widgetns in set(wp.get_widgets()) :
          globs['widget'] = wp
          break
      else :
        raise InvalidIdentifier('Cannot load widget provider for %s' % widgetns)

    def setUp(self):
      r"""Include the appropriate widget provider in global namespace 
      before running all test cases in the suite. In this case three
      objects are added to the global namespace :

        - `widget`       the component implementing the widget under test
        - `ctx`          context used to render the widget for 
                         anonymous user
        - `auth_ctx`     context used to render the widget for 
                         authenticated user
      """
      # Fail here if BloodhoundDashboardPlugin is not available. Thus 
      # this fact will be reported as a failure and subsequent test 
      # cases will be run anyway.
      from bhdashboard.api import DashboardSystem
      self.dbsys = DashboardSystem(self.env)

      # Add request objects
      DocTestTracLoader.doctestSuiteClass.setUp(self)

      widgetns = self.ns_from_name()
      if widgetns is None :
        # TODO: If doctests belong to a widget provider class then 
        #       instantiate it. In the mean time ...
        self.partial_setup()
      else :
        try :
          self.setup_widget(widgetns)
        except InvalidIdentifier:
          self.partial_setup()

  # Load trac built-in components and RPC handlers by default
  default_packages = ['trac']

#------------------------------------------------------
#    Helper functions used in test cases
#------------------------------------------------------

def clear_perm_cache(_env, _req):
  r"""Ensure that cache policies will not prevent test cases from 
  altering user permissions right away.
  """
  from trac.perm import PermissionSystem, DefaultPermissionPolicy

  _req.perm._cache.clear()            # Clear permission cache
  for policy in PermissionSystem(_env).policies :
    if isinstance(policy, DefaultPermissionPolicy):
      policy.permission_cache.clear() # Clear policy cache
      break

#------------------------------------------------------
#    Global test data
#------------------------------------------------------

from ConfigParser import RawConfigParser
from pkg_resources import resource_stream

def load_test_data(key):
  r"""Load data used for testing purposes. Currently such data is 
  stored in .INI files inside `data` directory.

  @param key          currently the path to the file containing the 
                      data, relative to `data` folder. 
  """
  fo = resource_stream(__name__, 'data/%s.ini' % key)
  try :
    p = RawConfigParser()
    p.readfp(fo)
    for section in p.sections():
      yield section, dict(p.items(section))
  finally :
    fo.close()

# The set of tickets used by test cases.
ticket_data = [(attrs.pop('summary'), attrs.pop('description'), attrs) \
                for _, attrs in sorted(load_test_data('ticket_data'))]

