#!/usr/bin/env python
# -*- coding: UTF-8 -*-

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

from trac.core import Component, implements
from trac.versioncontrol import Changeset
from trac.versioncontrol.api import (
    IRepositoryConnector, Repository, RepositoryManager)

from bhsearch.api import BloodhoundSearchApi
from bhsearch.search_resources.changeset_search import (
    ChangesetSearchParticipant)
from bhsearch.tests import unittest
from bhsearch.tests.base import BaseBloodhoundSearchTest
from bhsearch.whoosh_backend import WhooshBackend


class ChangesetIndexerEventsTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        super(ChangesetIndexerEventsTestCase, self).setUp()
        self.whoosh_backend = WhooshBackend(self.env)
        self.whoosh_backend.recreate_index()
        self.search_api = BloodhoundSearchApi(self.env)
        self.repository_manager = RepositoryManager(self.env)
        self.inject_dummy_repository()

    def test_can_index_added_changeset(self):
        rev = self.insert_changeset("Changed document 1.")

        results = self.search_api.query("*:*")

        self.assertEqual(1, results.hits)
        doc = results.docs[0]
        self.assertEqual('%s/dummy' % rev, doc["id"])
        self.assertEqual('dummy', doc["repository"])
        self.assertEqual('1', doc["revision"])
        self.assertEqual("Changed document 1.", doc["message"])

    def test_can_index_modified_changeset(self):
        rev = self.insert_changeset("Changed document 1.")
        self.modify_changeset(rev, "Added document 1.")

        results = self.search_api.query("*:*")

        self.assertEqual(1, results.hits)
        doc = results.docs[0]
        self.assertEqual('%s/dummy' % rev, doc["id"])
        self.assertEqual('dummy', doc["repository"])
        self.assertEqual('1', doc["revision"])
        self.assertEqual("Added document 1.", doc["message"])

    def insert_changeset(self, message, author=None, date=None, revision=None):
        rev = self.repository.add_changeset(revision, message, author, date)
        self.repository_manager.notify("changeset_added", 'dummy', [rev])
        return rev

    def modify_changeset(self, rev, message=None, author=None, date=None):
        changeset = self.repository.get_changeset(rev)
        if message is not None:
            changeset.message = message
        if author is not None:
            changeset.author = author
        if date is not None:
            changeset.date = date
        self.repository_manager.notify("changeset_modified", "dummy", [rev])

    def inject_dummy_repository(self):
        # pylint: disable=protected-access,attribute-defined-outside-init
        self.repository = DummyRepositry()
        self.repository_connector = DummyRepositoryConnector(self.env)
        self.repository_connector.repository = self.repository
        self.repository_manager._all_repositories = {
            'dummy': dict(dir='dirname', type='dummy')}
        self.repository_manager._connectors = {
            'dummy': (self.repository_connector, 100)}


class ChangesetSearchParticipantTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        super(ChangesetSearchParticipantTestCase, self).setUp()
        self.changeset_search = ChangesetSearchParticipant(self.env)

    def test_can_get_default_grid_fields(self):
        grid_fields = self.changeset_search.get_default_view_fields("grid")
        self.env.log.debug("grid_fields: %s", grid_fields)
        self.assertGreater(len(grid_fields), 0)

    def test_can_get_default_facets(self):
        default_facets = self.changeset_search.get_default_facets()
        self.env.log.debug("default_facets: %s", default_facets)
        self.assertIsNotNone(default_facets)

    def test_can_get_is_grid_view_defaults(self):
        default_grid_fields = self.changeset_search.get_default_view_fields(
            "grid")
        self.env.log.debug("default_grid_fields: %s", default_grid_fields)
        self.assertIsNotNone(default_grid_fields)

class DummyRepositoryConnector(Component):
    implements(IRepositoryConnector)

    repository = None

    def get_supported_types(self):
        return ('dummy', 100)

    def get_repository(self, repos_type, repos_dir, params):
        # pylint: disable=unused-argument
        return self.repository


class DummyRepositry(Repository):
    # pylint: disable=abstract-method
    name = "dummy.git"

    def __init__(self):
        super(DummyRepositry, self).__init__(
            "DummyRepo", dict(name='dummy', id='id'), None)
        self.changesets = {}
        self.revisions = []
        self.last_rev = 0

    def add_changeset(self, rev, message, author, date, changes=()):
        if rev is None:
            rev = self.last_rev = self.last_rev + 1
        changeset = Changeset(self, str(rev), message, author, date)
        changeset.get_changes = lambda: changes
        self.changesets[changeset.rev] = changeset
        self.revisions.append(changeset.rev)
        return str(rev)

    def get_changeset(self, rev):
        return self.changesets[rev]

    def get_changesets(self, start, stop):
        for rev in self.revisions:
            yield self.changesets[rev]

    def normalize_rev(self, rev):
        return rev

    def get_changes(self, old_path, old_rev, new_path, new_rev,
                    ignore_ancestry=1):
        return ()


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(
        unittest.makeSuite(ChangesetIndexerEventsTestCase, 'test'))
    test_suite.addTest(
        unittest.makeSuite(ChangesetSearchParticipantTestCase, 'test'))
    return test_suite

if __name__ == '__main__':
    unittest.main()
