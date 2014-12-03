# -*- coding: utf-8 -*-

from __future__ import with_statement

from datetime import datetime
import os.path
import shutil
from StringIO import StringIO
import tempfile
import unittest

from trac.attachment import Attachment
from trac.core import *
from trac.test import EnvironmentStub
from trac.tests.resource import TestResourceChangeListener
from trac.util.datefmt import utc, to_utimestamp
from trac.wiki import WikiPage, IWikiChangeListener


class TestWikiChangeListener(Component):

    implements(IWikiChangeListener)

    def __init__(self):
        self.added = []
        self.changed = []
        self.deleted = []
        self.deleted_version = []
        self.renamed = []

    def wiki_page_added(self, page):
        self.added.append(page)

    def wiki_page_changed(self, page, version, t, comment, author, ipnr):
        self.changed.append((page, version, t, comment, author, ipnr))

    def wiki_page_deleted(self, page):
        self.deleted.append(page)

    def wiki_page_version_deleted(self, page):
        self.deleted_version.append(page)

    def wiki_page_renamed(self, page, old_name):
        self.renamed.append((page, old_name))


class WikiPageTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        self.env.path = os.path.join(tempfile.gettempdir(), 'trac-tempenv')
        os.mkdir(self.env.path)

    def tearDown(self):
        shutil.rmtree(self.env.path)
        self.env.reset_db()

    def test_new_page(self):
        page = WikiPage(self.env)
        self.assertEqual(False, page.exists)
        self.assertEqual(None, page.name)
        self.assertEqual(0, page.version)
        self.assertEqual('', page.text)
        self.assertEqual(0, page.readonly)
        self.assertEqual('', page.author)
        self.assertEqual('', page.comment)
        self.assertEqual(None, page.time)

    def test_existing_page(self):
        t = datetime(2001, 1, 1, 1, 1, 1, 0, utc)
        self.env.db_transaction(
            "INSERT INTO wiki VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            ('TestPage', 1, to_utimestamp(t), 'joe', '::1', 'Bla bla',
             'Testing', 0))

        page = WikiPage(self.env, 'TestPage')
        self.assertEqual(True, page.exists)
        self.assertEqual('TestPage', page.name)
        self.assertEqual(1, page.version)
        self.assertEqual(None, page.resource.version)   # FIXME: Intentional?
        self.assertEqual('Bla bla', page.text)
        self.assertEqual(0, page.readonly)
        self.assertEqual('joe', page.author)
        self.assertEqual('Testing', page.comment)
        self.assertEqual(t, page.time)

        history = list(page.get_history())
        self.assertEqual(1, len(history))
        self.assertEqual((1, t, 'joe', 'Testing', '::1'), history[0])

        page = WikiPage(self.env, 'TestPage', 1)
        self.assertEqual(1, page.resource.version)

    def test_create_page(self):
        page = WikiPage(self.env)
        page.name = 'TestPage'
        page.text = 'Bla bla'
        t = datetime(2001, 1, 1, 1, 1, 1, 0, utc)
        page.save('joe', 'Testing', '::1', t)

        self.assertEqual(True, page.exists)
        self.assertEqual(1, page.version)
        self.assertEqual(1, page.resource.version)
        self.assertEqual(0, page.readonly)
        self.assertEqual('joe', page.author)
        self.assertEqual('Testing', page.comment)
        self.assertEqual(t, page.time)

        self.assertEqual(
            [(1, to_utimestamp(t), 'joe', '::1', 'Bla bla', 'Testing', 0)],
            self.env.db_query("""
                SELECT version, time, author, ipnr, text, comment, readonly
                FROM wiki WHERE name=%s
                """, ('TestPage',)))

        listener = TestWikiChangeListener(self.env)
        self.assertEqual(page, listener.added[0])

    def test_update_page(self):
        t = datetime(2001, 1, 1, 1, 1, 1, 0, utc)
        t2 = datetime(2002, 1, 1, 1, 1, 1, 0, utc)
        self.env.db_transaction(
            "INSERT INTO wiki VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            ('TestPage', 1, to_utimestamp(t), 'joe', '::1', 'Bla bla',
             'Testing', 0))

        page = WikiPage(self.env, 'TestPage')
        page.text = 'Bla'
        page.save('kate', 'Changing', '192.168.0.101', t2)

        self.assertEqual(2, page.version)
        self.assertEqual(2, page.resource.version)
        self.assertEqual(0, page.readonly)
        self.assertEqual('kate', page.author)
        self.assertEqual('Changing', page.comment)
        self.assertEqual(t2, page.time)

        with self.env.db_query as db:
            rows = db("""
               SELECT version, time, author, ipnr, text, comment, readonly
               FROM wiki WHERE name=%s
               """, ('TestPage',))
            self.assertEqual(2, len(rows))
            self.assertEqual((1, to_utimestamp(t), 'joe', '::1', 'Bla bla',
                              'Testing', 0), rows[0])
            self.assertEqual((2, to_utimestamp(t2), 'kate', '192.168.0.101',
                              'Bla', 'Changing', 0), rows[1])

        listener = TestWikiChangeListener(self.env)
        self.assertEqual((page, 2, t2, 'Changing', 'kate', '192.168.0.101'),
                         listener.changed[0])

        page = WikiPage(self.env, 'TestPage')
        history = list(page.get_history())
        self.assertEqual(2, len(history))
        self.assertEqual((2, t2, 'kate', 'Changing', '192.168.0.101'),
                         history[0])
        self.assertEqual((1, t, 'joe', 'Testing', '::1'), history[1])

    def test_delete_page(self):
        self.env.db_transaction(
            "INSERT INTO wiki VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            ('TestPage', 1, 42, 'joe', '::1', 'Bla bla', 'Testing', 0))

        page = WikiPage(self.env, 'TestPage')
        page.delete()

        self.assertEqual(False, page.exists)

        self.assertEqual([], self.env.db_query("""
            SELECT version, time, author, ipnr, text, comment, readonly
            FROM wiki WHERE name=%s
            """, ('TestPage',)))

        listener = TestWikiChangeListener(self.env)
        self.assertEqual(page, listener.deleted[0])

    def test_delete_page_version(self):
        self.env.db_transaction.executemany(
            "INSERT INTO wiki VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            [('TestPage', 1, 42, 'joe', '::1', 'Bla bla', 'Testing', 0),
             ('TestPage', 2, 43, 'kate', '192.168.0.11', 'Bla', 'Changing', 0)])

        page = WikiPage(self.env, 'TestPage')
        page.delete(version=2)

        self.assertEqual(True, page.exists)
        self.assertEqual(
            [(1, 42, 'joe', '::1', 'Bla bla', 'Testing', 0)],
            self.env.db_query("""
                SELECT version, time, author, ipnr, text, comment, readonly
                FROM wiki WHERE name=%s
                """, ('TestPage',)))

        listener = TestWikiChangeListener(self.env)
        self.assertEqual(page, listener.deleted_version[0])

    def test_delete_page_last_version(self):
        self.env.db_transaction(
            "INSERT INTO wiki VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            ('TestPage', 1, 42, 'joe', '::1', 'Bla bla', 'Testing', 0))

        page = WikiPage(self.env, 'TestPage')
        page.delete(version=1)

        self.assertEqual(False, page.exists)

        self.assertEqual([], self.env.db_query("""
            SELECT version, time, author, ipnr, text, comment, readonly
            FROM wiki WHERE name=%s
            """, ('TestPage',)))

        listener = TestWikiChangeListener(self.env)
        self.assertEqual(page, listener.deleted[0])

    def test_rename_page(self):
        data = (1, 42, 'joe', '::1', 'Bla bla', 'Testing', 0)
        self.env.db_transaction(
            "INSERT INTO wiki VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            ('TestPage',) + data)
        attachment = Attachment(self.env, 'wiki', 'TestPage')
        attachment.insert('foo.txt', StringIO(), 0, 1)

        page = WikiPage(self.env, 'TestPage')
        page.rename('PageRenamed')
        self.assertEqual('PageRenamed', page.name)

        self.assertEqual([data], self.env.db_query("""
            SELECT version, time, author, ipnr, text, comment, readonly
            FROM wiki WHERE name=%s
            """, ('PageRenamed',)))

        attachments = Attachment.select(self.env, 'wiki', 'PageRenamed')
        self.assertEqual('foo.txt', attachments.next().filename)
        self.assertRaises(StopIteration, attachments.next)
        Attachment.delete_all(self.env, 'wiki', 'PageRenamed')

        old_page = WikiPage(self.env, 'TestPage')
        self.assertEqual(False, old_page.exists)


        self.assertEqual([], self.env.db_query("""
            SELECT version, time, author, ipnr, text, comment, readonly
            FROM wiki WHERE name=%s
            """, ('TestPage',)))

        listener = TestWikiChangeListener(self.env)
        self.assertEqual((page, 'TestPage'), listener.renamed[0])

    def test_invalid_page_name(self):
        invalid_names = ('../Page', 'Page/..', 'Page/////SubPage',
                         'Page/./SubPage', '/PagePrefix', 'PageSuffix/')

        for name in invalid_names:
            page = WikiPage(self.env)
            page.name = name
            page.text = 'Bla bla'
            t = datetime(2001, 1, 1, 1, 1, 1, 0, utc)
            self.assertRaises(TracError, page.save, 'joe', 'Testing', '::1', t)

        page = WikiPage(self.env)
        page.name = 'TestPage'
        page.text = 'Bla bla'
        t = datetime(2001, 1, 1, 1, 1, 1, 0, utc)
        page.save('joe', 'Testing', '::1', t)
        for name in invalid_names:
            page = WikiPage(self.env, 'TestPage')
            self.assertRaises(TracError, page.rename, name)

class WikiResourceChangeListenerTestCase(unittest.TestCase):
    INITIAL_NAME = "Wiki page 1"
    INITIAL_TEXT = "some text"
    INITIAL_AUTHOR = "anAuthor"
    INITIAL_COMMENT = "some comment"
    INITIAL_REMOTE_ADDRESS = "::1"

    def setUp(self):
        self.env = EnvironmentStub(default_data=True)
        self.listener = TestResourceChangeListener(self.env)
        self.listener.resource_type = WikiPage
        self.listener.callback = self.listener_callback

    def tearDown(self):
        self.env.reset_db()

    def test_change_listener_created(self):
        self._create_wiki_page(self.INITIAL_NAME)
        self.assertEqual('created', self.listener.action)
        self.assertTrue(isinstance(self.listener.resource, WikiPage))
        self.assertEqual(self.INITIAL_NAME, self.wiki_name)
        self.assertEqual(self.INITIAL_TEXT, self.wiki_text)

    def test_change_listener_text_changed(self):
        wiki_page = self._create_wiki_page(self.INITIAL_NAME)
        CHANGED_TEXT = "some other text"
        wiki_page.text = CHANGED_TEXT
        wiki_page.save("author1", "renamed_comment", "::2")
        self.assertEqual('changed', self.listener.action)
        self.assertTrue(isinstance(self.listener.resource, WikiPage))
        self.assertEqual(self.INITIAL_NAME, self.wiki_name)
        self.assertEqual(CHANGED_TEXT, self.wiki_text)
        self.assertEqual({"text":self.INITIAL_TEXT}, self.listener.old_values)

    def test_change_listener_renamed(self):
        wiki_page = self._create_wiki_page(self.INITIAL_NAME)
        CHANGED_NAME = "NewWikiName"
        wiki_page.rename(CHANGED_NAME)
        self.assertEqual('changed', self.listener.action)
        self.assertTrue(isinstance(self.listener.resource, WikiPage))
        self.assertEqual(CHANGED_NAME, self.wiki_name)
        self.assertEqual(self.INITIAL_TEXT, self.wiki_text)
        self.assertEqual({"name":self.INITIAL_NAME}, self.listener.old_values)

    def test_change_listener_deleted(self):
        wiki_page = self._create_wiki_page(self.INITIAL_NAME)
        wiki_page.delete()
        self.assertEqual('deleted', self.listener.action)
        self.assertTrue(isinstance(self.listener.resource, WikiPage))
        self.assertEqual(self.INITIAL_NAME, self.wiki_name)

    def _create_wiki_page(self, name=None):
        name = name or self.INITIAL_NAME
        wiki_page = WikiPage(self.env, name)
        wiki_page.text = self.INITIAL_TEXT
        wiki_page.save(
            self.INITIAL_AUTHOR,
            self.INITIAL_COMMENT,
            self.INITIAL_REMOTE_ADDRESS)
        return wiki_page

    def listener_callback(self, action, resource, context, old_values = None):
        self.wiki_name = resource.name
        self.wiki_text = resource.text

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(WikiPageTestCase, 'test'))
    suite.addTest(unittest.makeSuite(
        WikiResourceChangeListenerTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
