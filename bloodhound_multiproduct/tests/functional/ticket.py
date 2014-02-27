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

"""Override a few functional tests for tickets.
"""

from urlparse import urlsplit

from twill.errors import TwillException

from trac.ticket.tests.functional import *

from tests import unittest
from tests.functional import regex_owned_by

#----------------
# Functional test cases for tickets (rewritten)
#----------------

# TODO: These classes are almost a copycat of Trac's. Beware of license header

class TestTicketPreview(FunctionalTwillTestCaseSetup):
    """There's no such thing like ticket preview in Bloodhound but, if it would
    then the corresponding Trac test case should be rewritten like this.
    """
    def runTest(self):
        """Preview ticket creation
        """
        # [BLOODHOUND] New Ticket => More fields (in create ticket menu)
        self._tester.go_to_newticket()

        summary = random_sentence(5)
        desc = random_sentence(5)
        tc.formvalue('propertyform', 'field-summary', summary)
        tc.formvalue('propertyform', 'field-description', desc)
        tc.submit('preview')
        tc.url(self._tester.url + '/newticket$')
        tc.find('ticket not yet created')
        tc.find(summary)
        tc.find(desc)


class TestTicketNoSummary(FunctionalTwillTestCaseSetup):
    def runTest(self):
        """Creating a ticket without summary should fail
        """
        # [BLOODHOUND] New Ticket => More fields (in create ticket menu)
        self._tester.go_to_newticket()

        desc = random_sentence(5)
        tc.formvalue('propertyform', 'field-description', desc)
        # [BLOODHOUND] no actual button to submit /newticket `propertyform`
        tc.submit()
        tc.find(desc)
        tc.find('Tickets must contain a summary.')
        # [BLOODHOUND] Create New Ticket => New Ticket
        tc.find('New Ticket')
        tc.find('ticket not yet created')


class TestTicketCustomFieldTextNoFormat(FunctionalTwillTestCaseSetup):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test custom text field with no format explicitly specified.
        Its contents should be rendered as plain text.
        """
        env = self._testenv.get_trac_environment()
        env.config.set('ticket-custom', 'newfield', 'text')
        env.config.set('ticket-custom', 'newfield.label',
                       'Another Custom Field')
        env.config.set('ticket-custom', 'newfield.format', '')
        env.config.save()

        self._testenv.restart()
        val = "%s %s" % (random_unique_camel(), random_word())
        ticketid = self._tester.create_ticket(summary=random_sentence(3),
                                              info={'newfield': val})
        self._tester.go_to_ticket(ticketid)

        # [BLOODHOUND] Different markup to render field values
        self._tester.find_ticket_field('newfield', val)


class TestTicketCustomFieldTextAreaNoFormat(FunctionalTwillTestCaseSetup):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test custom textarea field with no format explicitly specified,
        its contents should be rendered as plain text.
        """
        env = self._testenv.get_trac_environment()
        env.config.set('ticket-custom', 'newfield', 'textarea')
        env.config.set('ticket-custom', 'newfield.label',
                       'Another Custom Field')
        env.config.set('ticket-custom', 'newfield.format', '')
        env.config.save()

        self._testenv.restart()
        val = "%s %s" % (random_unique_camel(), random_word())
        ticketid = self._tester.create_ticket(summary=random_sentence(3),
                                              info={'newfield': val})
        self._tester.go_to_ticket(ticketid)

        # [BLOODHOUND] Different markup to render field values
        self._tester.find_ticket_field('newfield', val)


class TestTicketCustomFieldTextWikiFormat(FunctionalTwillTestCaseSetup):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test custom text field with `wiki` format.
        Its contents should through the wiki engine, wiki-links and all.
        Feature added in http://trac.edgewall.org/ticket/1791
        """
        env = self._testenv.get_trac_environment()
        env.config.set('ticket-custom', 'newfield', 'text')
        env.config.set('ticket-custom', 'newfield.label',
                       'Another Custom Field')
        env.config.set('ticket-custom', 'newfield.format', 'wiki')
        env.config.save()

        self._testenv.restart()
        word1 = random_unique_camel()
        word2 = random_word()
        val = "%s %s" % (word1, word2)
        ticketid = self._tester.create_ticket(summary=random_sentence(3),
                                              info={'newfield': val})
        self._tester.go_to_ticket(ticketid)
        wiki = '<a [^>]*>%s\??</a> %s' % (word1, word2)

        # [BLOODHOUND] Different markup to render field values
        self._tester.find_ticket_field('newfield', wiki)


class TestTicketCustomFieldTextAreaWikiFormat(FunctionalTwillTestCaseSetup):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test custom textarea field with no format explicitly specified,
        its contents should be rendered as plain text.
        """
        env = self._testenv.get_trac_environment()
        env.config.set('ticket-custom', 'newfield', 'textarea')
        env.config.set('ticket-custom', 'newfield.label',
                       'Another Custom Field')
        env.config.set('ticket-custom', 'newfield.format', 'wiki')
        env.config.save()

        self._testenv.restart()
        word1 = random_unique_camel()
        word2 = random_word()
        val = "%s %s" % (word1, word2)
        ticketid = self._tester.create_ticket(summary=random_sentence(3),
                                              info={'newfield': val})
        self._tester.go_to_ticket(ticketid)
        wiki = '<p>\s*<a [^>]*>%s\??</a> %s<br />\s*</p>' % (word1, word2)

        # [BLOODHOUND] Different markup to render field values
        self._tester.find_ticket_field('newfield', wiki)


class TestTicketCustomFieldTextReferenceFormat(FunctionalTwillTestCaseSetup):
    # Run this test case in default product context to keep body agnostic to
    # context switching
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test custom text field with `reference` format.
        Its contents are treated as a single value
        and are rendered as an auto-query link.
        Feature added in http://trac.edgewall.org/ticket/10643
        """
        env = self._testenv.get_trac_environment()
        env.config.set('ticket-custom', 'newfield', 'text')
        env.config.set('ticket-custom', 'newfield.label',
                       'Another Custom Field')
        env.config.set('ticket-custom', 'newfield.format', 'reference')
        env.config.save()

        self._testenv.restart()
        word1 = random_unique_camel()
        word2 = random_word()
        val = "%s %s" % (word1, word2)
        ticketid = self._tester.create_ticket(summary=random_sentence(3),
                                              info={'newfield': val})
        self._tester.go_to_ticket(ticketid)
        query = 'status=!closed&amp;newfield=%s\+%s' % (word1, word2)

        path_prefix = urlsplit(self._tester.url).path
        querylink = '<a href="%s/query\?%s">%s</a>' % (path_prefix, query, val)

        # [BLOODHOUND] Different markup to render field values
        self._tester.find_ticket_field('newfield', querylink)


class TestTicketCustomFieldTextListFormat(FunctionalTwillTestCaseSetup):
    # Run this test case in default product context to keep body agnostic to
    # context switching
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test custom text field with `list` format.
        Its contents are treated as a space-separated list of values
        and are rendered as separate auto-query links per word.
        Feature added in http://trac.edgewall.org/ticket/10643
        """
        env = self._testenv.get_trac_environment()
        env.config.set('ticket-custom', 'newfield', 'text')
        env.config.set('ticket-custom', 'newfield.label',
                       'Another Custom Field')
        env.config.set('ticket-custom', 'newfield.format', 'list')
        env.config.save()

        self._testenv.restart()
        word1 = random_unique_camel()
        word2 = random_word()
        val = "%s %s" % (word1, word2)
        ticketid = self._tester.create_ticket(summary=random_sentence(3),
                                              info={'newfield': val})
        self._tester.go_to_ticket(ticketid)
        query1 = 'status=!closed&amp;newfield=~%s' % word1
        query2 = 'status=!closed&amp;newfield=~%s' % word2

        path_prefix = urlsplit(self._tester.url).path
        querylink1 = '<a href="%s/query\?%s">%s</a>' % (path_prefix,
                                                        query1, word1)
        querylink2 = '<a href="%s/query\?%s">%s</a>' % (path_prefix,
                                                        query2, word2)
        querylinks = '%s %s' % (querylink1, querylink2)

        # [BLOODHOUND] Different markup to render field values
        self._tester.find_ticket_field('newfield', querylinks)


class RegressionTestTicket10828(FunctionalTwillTestCaseSetup):
    # Run this test case in default product context to keep body agnostic to
    # context switching
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test for regression of http://trac.edgewall.org/ticket/10828
        Rendered property changes should be described as lists of added and
        removed items, even in the presence of comma and semicolon separators.
        """
        env = self._testenv.get_trac_environment()
        env.config.set('ticket-custom', 'newfield', 'text')
        env.config.set('ticket-custom', 'newfield.label',
                       'A Custom Field')
        env.config.set('ticket-custom', 'newfield.format', 'list')
        env.config.save()

        self._testenv.restart()
        ticketid = self._tester.create_ticket(summary=random_sentence(3))
        self._tester.go_to_ticket(ticketid)

        word1 = random_unique_camel()
        word2 = random_word()
        val = "%s %s" % (word1, word2)
        tc.formvalue('propertyform', 'field-newfield', val)
        tc.submit('submit')
        tc.find('<em>%s</em> <em>%s</em> added' % (word1, word2))

        word3 = random_unique_camel()
        word4 = random_unique_camel()
        val = "%s,  %s; %s" % (word2, word3, word4)
        tc.formvalue('propertyform', 'field-newfield', val)
        tc.submit('submit')
        tc.find('<em>%s</em> <em>%s</em> added; <em>%s</em> removed'
                % (word3, word4, word1))

        tc.formvalue('propertyform', 'field-newfield', '')
        tc.submit('submit')
        tc.find('<em>%s</em> <em>%s</em> <em>%s</em> removed'
                % (word2, word3, word4))

        val = "%s %s,%s" % (word1, word2, word3)
        tc.formvalue('propertyform', 'field-newfield', val)
        tc.submit('submit')
        tc.find('<em>%s</em> <em>%s</em> <em>%s</em> added'
                % (word1, word2, word3))
        query1 = 'status=!closed&amp;newfield=~%s' % word1
        query2 = 'status=!closed&amp;newfield=~%s' % word2
        query3 = 'status=!closed&amp;newfield=~%s' % word3


        path_prefix = urlsplit(self._tester.url).path
        querylink1 = '<a href="%s/query\?%s">%s</a>' % (path_prefix,
                                                        query1, word1)
        querylink2 = '<a href="%s/query\?%s">%s</a>' % (path_prefix,
                                                        query2, word2)
        querylink3 = '<a href="%s/query\?%s">%s</a>' % (path_prefix,
                                                        query3, word3)
        querylinks = '%s %s, %s' % (querylink1, querylink2, querylink3)

        # [BLOODHOUND] Different markup to render field values
        self._tester.find_ticket_field('newfield', querylinks)


class RegressionTestTicket5394a(FunctionalTwillTestCaseSetup):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test for regression of http://trac.edgewall.org/ticket/5394 a
        Order user list alphabetically in (re)assign action
        """
        # set restrict_owner config
        env = self._testenv.get_trac_environment()
        env.config.set('ticket', 'restrict_owner', 'yes')
        env.config.save()
        self._testenv.restart()

        self._tester.go_to_front()
        self._tester.logout()

        test_users = ['alice', 'bob', 'jane', 'john', 'charlie', 'alan',
                      'zorro']
        # Apprently it takes a sec for the new user to be recognized by the
        # environment.  So we add all the users, then log in as the users
        # in a second loop.  This should be faster than adding a sleep(1)
        # between the .adduser and .login steps.
        for user in test_users:
            self._testenv.adduser(user)
        for user in test_users:
            self._tester.login(user)
            self._tester.logout()

        self._tester.login('admin')

        ticketid = self._tester.create_ticket("regression test 5394a")
        self._tester.go_to_ticket(ticketid)

        # [BLOODHOUND] Workflow <select /> does not end with id attribute
        options = 'id="action_reassign_reassign_owner"[^>]*>' + \
            ''.join(['<option[^>]*>%s</option>' % user for user in
                     sorted(test_users + ['admin', 'user'])])
        tc.find(options, 's')
        # We don't have a good way to fully delete a user from the Trac db.
        # Once we do, we may want to cleanup our list of users here.


class RegressionTestTicket5394b(FunctionalTwillTestCaseSetup):
    def runTest(self):
        """Test for regression of http://trac.edgewall.org/ticket/5394 b
        Order user list alphabetically on new ticket page
        """
        #FIXME : Test is missing a lot of context. See RegressionTestTicket5394a

        # Must run after RegressionTestTicket5394a
        self._tester.go_to_front()

        # [BLOODHOUND] New Ticket => More fields (in create ticket menu)
        self._tester.go_to_newticket()
        # [BLOODHOUND] Create New Ticket => New Ticket
        tc.find('New Ticket')

        test_users = ['alice', 'bob', 'jane', 'john', 'charlie', 'alan',
                      'zorro']
        options = 'id="field-owner"[^>]*>[[:space:]]*<option/>.*' + \
            '.*'.join(['<option[^>]*>%s</option>' % user for user in
                     sorted(test_users + ['admin', 'user'])])
        options = '.*'.join(sorted(test_users + ['admin', 'user']))
        tc.find(options, 's')

# FIXME: Verbatim copy of its peer just to override regex_owned_by
class RegressionTestTicket5497a(FunctionalTwillTestCaseSetup):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test for regression of http://trac.edgewall.org/ticket/5497 a
        Open ticket, component changed, owner not changed"""
        ticketid = self._tester.create_ticket("regression test 5497a")
        self._tester.go_to_ticket(ticketid)
        tc.formvalue('propertyform', 'field-component', 'regression5497')
        tc.submit('submit')
        tc.find(regex_owned_by('user'))


# FIXME: Verbatim copy of its peer just to override regex_owned_by
class RegressionTestTicket5497b(FunctionalTwillTestCaseSetup):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test for regression of http://trac.edgewall.org/ticket/5497 b
        Open ticket, component changed, owner changed"""
        ticketid = self._tester.create_ticket("regression test 5497b")
        self._tester.go_to_ticket(ticketid)
        tc.formvalue('propertyform', 'field-component', 'regression5497')
        tc.formvalue('propertyform', 'action', 'reassign')
        tc.formvalue('propertyform', 'action_reassign_reassign_owner', 'admin')
        tc.submit('submit')
        tc.notfind(regex_owned_by('user'))
        tc.find(regex_owned_by('admin'))


# FIXME: Verbatim copy of its peer just to override regex_owned_by
class RegressionTestTicket5497c(FunctionalTwillTestCaseSetup):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test for regression of http://trac.edgewall.org/ticket/5497 c
        New ticket, component changed, owner not changed"""
        ticketid = self._tester.create_ticket("regression test 5497c",
            {'component':'regression5497'})
        self._tester.go_to_ticket(ticketid)
        tc.find(regex_owned_by('user'))


# FIXME: Verbatim copy of its peer just to override regex_owned_by
class RegressionTestTicket5497d(FunctionalTwillTestCaseSetup):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test for regression of http://trac.edgewall.org/ticket/5497 d
        New ticket, component changed, owner changed"""
        ticketid = self._tester.create_ticket("regression test 5497d",
            {'component':'regression5497', 'owner':'admin'})
        self._tester.go_to_ticket(ticketid)
        tc.find(regex_owned_by('admin'))

class RegressionTestRev5994(FunctionalTwillTestCaseSetup):
    def runTest(self):
        """Test for regression of the column label fix in r5994"""
        env = self._testenv.get_trac_environment()
        env.config.set('ticket-custom', 'custfield', 'text')
        env.config.set('ticket-custom', 'custfield.label', 'Custom Field')
        env.config.save()
        try:
            self._testenv.restart()
            self._tester.go_to_query()
            self._tester.find_query_column_selector('custfield', 'Custom Field')
        finally:
            pass
            #env.config.set('ticket', 'restrict_owner', 'no')
            #env.config.save()
            #self._testenv.restart()


class RegressionTestTicket6048(FunctionalTwillTestCaseSetup):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test for regression of http://trac.edgewall.org/ticket/6048"""
        # Setup the DeleteTicket plugin
        plugin = open(os.path.join(self._testenv.command_cwd, 'sample-plugins',
                                   'workflow', 'DeleteTicket.py')).read()
        open(os.path.join(self._testenv.tracdir, 'plugins', 'DeleteTicket.py'),
             'w').write(plugin)
        env = self._testenv.get_trac_environment()

        # [BLOODHOUND] Ensure plugin will be enabled in target scope
        env.config.set('components', 'DeleteTicket.*', 'enabled')

        prevconfig = env.config.get('ticket', 'workflow')
        env.config.set('ticket', 'workflow',
                       prevconfig + ',DeleteTicketActionController')
        env.config.save()
        env = self._testenv.get_trac_environment() # reload environment

        # Create a ticket and delete it
        ticket_id = self._tester.create_ticket(
            summary='RegressionTestTicket6048')
        # (Create a second ticket so that the ticket id does not get reused
        # and confuse the tester object.)
        self._tester.create_ticket(summary='RegressionTestTicket6048b')
        self._tester.go_to_ticket(ticket_id)
        tc.find('delete ticket')
        tc.formvalue('propertyform', 'action', 'delete')
        tc.submit('submit')

        self._tester.go_to_ticket(ticket_id)
        tc.find('Error: Invalid ticket number')
        tc.find('Ticket %s does not exist.' % ticket_id)

        # Remove the DeleteTicket plugin
        env.config.set('ticket', 'workflow', prevconfig)
        env.config.save()
        env = self._testenv.get_trac_environment() # reload environment
        for ext in ('py', 'pyc', 'pyo'):
            filename = os.path.join(self._testenv.tracdir, 'plugins',
                                    'DeleteTicket.%s' % ext)
            if os.path.exists(filename):
                os.unlink(filename)


class RegressionTestTicket7821group(FunctionalTwillTestCaseSetup):
    def runTest(self):
        """Test for regression of http://trac.edgewall.org/ticket/7821 group"""
        env = self._testenv.get_trac_environment()
        saved_default_query = env.config.get('query', 'default_query')
        default_query = 'status!=closed&order=status&group=status&max=42' \
                        '&desc=1&groupdesc=1&col=summary|status|cc' \
                        '&cc~=$USER'
        env.config.set('query', 'default_query', default_query)
        env.config.save()
        try:
            self._testenv.restart()
            self._tester.create_ticket('RegressionTestTicket7821 group')
            self._tester.go_to_query()
            # $USER
            tc.find('<input type="text" name="0_cc" value="admin"'
                    ' size="[0-9]+" />')
            # col
            tc.find('<input type="checkbox" name="col" value="summary"'
                    ' checked="checked" />')
            tc.find('<input type="checkbox" name="col" value="owner" />')
            tc.find('<input type="checkbox" name="col" value="status"'
                    ' checked="checked" />')
            tc.find('<input type="checkbox" name="col" value="cc"'
                    ' checked="checked" />')
            # group
            tc.find('<option selected="selected" value="status">Status'
                    '</option>')
            # groupdesc
            tc.find('<input type="checkbox" name="groupdesc" id="groupdesc"'
                    ' checked="checked" />')
            # max
            # [BLOODHOUND] class="input-mini" added (Twitter Bootstrap)
            tc.find('<input type="text" name="max" id="max" size="[0-9]*?"'
                    ' value="42" [^/]*/>')
            # col in results
            tc.find('<a title="Sort by Ticket [(]ascending[)]" ')
            tc.find('<a title="Sort by Summary [(]ascending[)]" ')
            tc.find('<a title="Sort by Status [(]ascending[)]" ')
            tc.find('<a title="Sort by Cc [(]ascending[)]" ')
            tc.notfind('<a title="Sort by Owner "')
        finally:
            env.config.set('query', 'default_query', saved_default_query)
            env.config.save()
            self._testenv.restart()


class RegressionTestTicket8247(FunctionalTwillTestCaseSetup):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test for regression of http://trac.edgewall.org/ticket/8247
        Author field of ticket comment corresponding to the milestone removal
        was always 'anonymous'.
        """
        name = "MilestoneRemove"
        self._tester.create_milestone(name)
        id = self._tester.create_ticket(info={'milestone': name})
        ticket_url = self._tester.url + "/ticket/%d" % id
        tc.go(ticket_url)
        tc.find(name)
        tc.go(self._tester.url + "/admin/ticket/milestones")
        tc.formvalue('milestone_table', 'sel', name)
        tc.submit('remove')
        tc.go(ticket_url)

        # [BLOODHOUND] Ticket comment header changed
        tc.find('<strong class="trac-field-milestone">Milestone</strong>'
                '[ \n\t]*<span>[ \n\t]*<em>%s</em> deleted' % name)
        tc.find('by admin<span>, <a.* ago</a></span>')

        tc.notfind('anonymous')


class TestTimelineTicketDetails(FunctionalTwillTestCaseSetup):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test ticket details on timeline"""
        env = self._testenv.get_trac_environment()
        env.config.set('timeline', 'ticket_show_details', 'yes')
        env.config.save()
        summary = random_sentence(5)
        ticketid = self._tester.create_ticket(summary)
        self._tester.go_to_ticket(ticketid)
        self._tester.add_comment(ticketid)
        self._tester.go_to_timeline()
        tc.formvalue('prefs', 'ticket_details', True)
        tc.submit()
        htmltags = '(<[^>]*>)*'

        # [BLOODHOUND] Ticket events are different i.e. 'by user' outside <a />
        tc.find(htmltags + 'Ticket ' + htmltags + '#' + str(ticketid) +
                htmltags + ' \\(' + summary + '\\) updated\\s*' +
                htmltags + '\\s+by\\s+' + htmltags + 'admin', 's')


class TestTicketHistoryDiff(FunctionalTwillTestCaseSetup):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test ticket history (diff)"""
        name = 'TestTicketHistoryDiff'
        ticketid = self._tester.create_ticket(name)
        self._tester.go_to_ticket(ticketid)
        tc.formvalue('propertyform', 'description', random_sentence(6))
        tc.submit('submit')

        # [BLOODHOUND] Description 'modified' in comments feed inside <span />
        tc.find('Description<[^>]*>\\s*<[^>]*>\\s*modified \\(<[^>]*>diff', 's')
        tc.follow('diff')
        tc.find('Changes\\s*between\\s*<[^>]*>Initial Version<[^>]*>\\s*and' \
                '\\s*<[^>]*>Version 1<[^>]*>\\s*of\\s*<[^>]*>Ticket #' , 's')


class RegressionTestTicket5602(FunctionalTwillTestCaseSetup):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test for regression of http://trac.edgewall.org/ticket/5602"""
        # Create a set of tickets, and assign them all to a milestone
        milestone = self._tester.create_milestone()
        ids = [self._tester.create_ticket() for x in range(5)]
        [self._tester.ticket_set_milestone(x, milestone) for x in ids]
        # Need a ticket in each state: new, assigned, accepted, closed,
        # reopened
        # leave ids[0] as new
        # make ids[1] be assigned
        self._tester.go_to_ticket(ids[1])
        tc.formvalue('propertyform', 'action', 'reassign')
        tc.formvalue('propertyform', 'action_reassign_reassign_owner', 'admin')
        tc.submit('submit')
        # make ids[2] be accepted
        self._tester.go_to_ticket(ids[2])
        tc.formvalue('propertyform', 'action', 'accept')
        tc.submit('submit')
        # make ids[3] be closed
        self._tester.go_to_ticket(ids[3])
        tc.formvalue('propertyform', 'action', 'resolve')
        tc.formvalue('propertyform', 'action_resolve_resolve_resolution', 'fixed')
        tc.submit('submit')
        # make ids[4] be reopened
        self._tester.go_to_ticket(ids[4])
        tc.formvalue('propertyform', 'action', 'resolve')
        tc.formvalue('propertyform', 'action_resolve_resolve_resolution', 'fixed')
        tc.submit('submit')
        # FIXME: we have to wait a second to avoid "IntegrityError: columns
        # ticket, time, field are not unique"
        time.sleep(1)
        tc.formvalue('propertyform', 'action', 'reopen')
        tc.submit('submit')
        tc.show()
        tc.notfind("Python Traceback")

        # Go to the milestone and follow the links to the closed and active
        # tickets.
        tc.go(self._tester.url + "/roadmap")
        tc.follow(milestone)

        # [BLOODHOUND] closed: labels in milestone progress bar removed
        tc.follow(r"/query\?.*status=closed&.*milestone=%s$" % (milestone,))
        tc.find("Resolution:[ \t\n]+fixed")

        tc.back()
        # [BLOODHOUND] active: labels in milestone progress bar removed
        tc.follow(r"/query\?.*status=new&.*milestone=%s$" % (milestone,))
        tc.find("Status:[ \t\n]+new")
        tc.find("Status:[ \t\n]+assigned")
        tc.find("Status:[ \t\n]+accepted")
        tc.notfind("Status:[ \t\n]+closed")
        tc.find("Status:[ \t\n]+reopened")


class RegressionTestTicket9084(FunctionalTwillTestCaseSetup):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test for regression of http://trac.edgewall.org/ticket/9084"""
        ticketid = self._tester.create_ticket()
        self._tester.add_comment(ticketid)
        self._tester.go_to_ticket(ticketid)
        tc.submit('2', formname='reply-to-comment-1') # '1' hidden, '2' submit
        tc.formvalue('propertyform', 'comment', random_sentence(3))

        # [BLOODHPUND] In ticket comments reply form 'Submit changes'=>'Submit'
        tc.submit('Submit')
        tc.notfind('AssertionError')


class RegressionTestTicket6879a(FunctionalTwillTestCaseSetup,
                                unittest.TestCase):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test for regression of http://trac.edgewall.org/ticket/6879 a

        Make sure that previewing a close does not make the available actions
        be those for the close status.
        """
        # create a ticket, then preview resolving the ticket twice
        ticket_id = self._tester.create_ticket("RegressionTestTicket6879 a")
        self._tester.go_to_ticket(ticket_id)
        tc.formvalue('propertyform', 'action', 'resolve')
        tc.formvalue('propertyform', 'action_resolve_resolve_resolution', 'fixed')

        # [BLOODHOUND] No preview button for ticket (comments) in BH theme
        try:
            tc.submit('preview')
        except TwillException:
            self.skipTest('Active theme without ticket preview')

        tc.formvalue('propertyform', 'action', 'resolve')
        tc.submit('preview')


class RegressionTestTicket6879b(FunctionalTwillTestCaseSetup,
                                unittest.TestCase):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Test for regression of http://trac.edgewall.org/ticket/6879 b

        Make sure that previewing a close does not make the available actions
        be those for the close status.
        """
        # create a ticket, then preview resolving the ticket twice
        ticket_id = self._tester.create_ticket("RegressionTestTicket6879 b")
        self._tester.go_to_ticket(ticket_id)
        tc.formvalue('propertyform', 'action', 'resolve')
        tc.formvalue('propertyform', 'action_resolve_resolve_resolution', 'fixed')

        # [BLOODHOUND] No preview button for ticket (comments) in BH theme
        try:
            tc.submit('preview')
        except TwillException:
            self.skipTest('Active theme without ticket comment preview')

        tc.formvalue('propertyform', 'action', 'resolve')
        tc.submit('submit')


class TestAdminPriorityRenumber(FunctionalTwillTestCaseSetup):
    BH_IN_DEFAULT_PRODUCT = True

    def runTest(self):
        """Admin renumber priorities"""

        # [BLOODHOUND] class="input-mini" appended to priorities <select />
        valuesRE = re.compile('<select name="value_([0-9]+)".*>', re.M)

        html = b.get_html()
        max_priority = max([int(x) for x in valuesRE.findall(html)])

        name = "RenumberPriority"
        self._tester.create_priority(name + '1')
        self._tester.create_priority(name + '2')
        priority_url = self._tester.url + '/admin/ticket/priority'
        tc.go(priority_url)
        tc.url(priority_url + '$')
        tc.find(name + '1')
        tc.find(name + '2')
        tc.formvalue('enumtable', 'value_%s' % (max_priority + 1), str(max_priority + 2))
        tc.formvalue('enumtable', 'value_%s' % (max_priority + 2), str(max_priority + 1))
        tc.submit('apply')
        tc.url(priority_url + '$')
        # Verify that their order has changed.
        tc.find(name + '2.*' + name + '1', 's')


# Ensure that overridden code will be loaded
def trac_functionalSuite(suite=None):
    suite.addTest(TestTickets())

    # [BLOODHOUND] there's no such thing like ticket preview
    #suite.addTest(TestTicketPreview())

    suite.addTest(TestTicketNoSummary())
    suite.addTest(TestTicketAltFormats())
    suite.addTest(TestTicketCSVFormat())
    suite.addTest(TestTicketTabFormat())
    suite.addTest(TestTicketRSSFormat())

    # [BLOODHOUND] TODO: Move to BloodhoundSearch plugin
    # suite.addTest(TestTicketSearch())
    # suite.addTest(TestNonTicketSearch())

    suite.addTest(TestTicketHistory())
    suite.addTest(TestTicketHistoryDiff())
    suite.addTest(TestTicketQueryLinks())
    suite.addTest(TestTicketQueryOrClause())
    suite.addTest(TestTicketCustomFieldTextNoFormat())
    suite.addTest(TestTicketCustomFieldTextWikiFormat())
    suite.addTest(TestTicketCustomFieldTextAreaNoFormat())
    suite.addTest(TestTicketCustomFieldTextAreaWikiFormat())
    suite.addTest(TestTicketCustomFieldTextReferenceFormat())
    suite.addTest(TestTicketCustomFieldTextListFormat())
    suite.addTest(RegressionTestTicket10828())
    suite.addTest(TestTimelineTicketDetails())
    suite.addTest(TestAdminComponent())
    suite.addTest(TestAdminComponentDuplicates())
    suite.addTest(TestAdminComponentRemoval())
    suite.addTest(TestAdminComponentNonRemoval())
    suite.addTest(TestAdminComponentDefault())
    suite.addTest(TestAdminComponentDetail())
    suite.addTest(TestAdminMilestone())
    suite.addTest(TestAdminMilestoneSpace())
    suite.addTest(TestAdminMilestoneDuplicates())
    suite.addTest(TestAdminMilestoneDetail())
    suite.addTest(TestAdminMilestoneDue())
    suite.addTest(TestAdminMilestoneDetailDue())
    suite.addTest(TestAdminMilestoneCompleted())
    suite.addTest(TestAdminMilestoneCompletedFuture())
    suite.addTest(TestAdminMilestoneRemove())
    suite.addTest(TestAdminMilestoneRemoveMulti())
    suite.addTest(TestAdminMilestoneNonRemoval())
    suite.addTest(TestAdminMilestoneDefault())
    suite.addTest(TestAdminPriority())
    suite.addTest(TestAdminPriorityModify())
    suite.addTest(TestAdminPriorityRemove())
    suite.addTest(TestAdminPriorityRemoveMulti())
    suite.addTest(TestAdminPriorityNonRemoval())
    suite.addTest(TestAdminPriorityDefault())
    suite.addTest(TestAdminPriorityDetail())
    suite.addTest(TestAdminPriorityRenumber())
    suite.addTest(TestAdminPriorityRenumberDup())
    suite.addTest(TestAdminResolution())
    suite.addTest(TestAdminResolutionDuplicates())
    suite.addTest(TestAdminSeverity())
    suite.addTest(TestAdminSeverityDuplicates())
    suite.addTest(TestAdminType())
    suite.addTest(TestAdminTypeDuplicates())
    suite.addTest(TestAdminVersion())
    suite.addTest(TestAdminVersionDuplicates())
    suite.addTest(TestAdminVersionDetail())
    suite.addTest(TestAdminVersionDetailTime())
    suite.addTest(TestAdminVersionDetailCancel())
    suite.addTest(TestAdminVersionRemove())
    suite.addTest(TestAdminVersionRemoveMulti())
    suite.addTest(TestAdminVersionNonRemoval())
    suite.addTest(TestAdminVersionDefault())
    suite.addTest(TestNewReport())
    suite.addTest(TestReportRealmDecoration())
    suite.addTest(RegressionTestRev5665())
    suite.addTest(RegressionTestRev5994())

    suite.addTest(RegressionTestTicket4447())
    suite.addTest(RegressionTestTicket4630a())
    suite.addTest(RegressionTestTicket4630b())
    suite.addTest(RegressionTestTicket5022())
    suite.addTest(RegressionTestTicket5394a())
    suite.addTest(RegressionTestTicket5394b())
    suite.addTest(RegressionTestTicket5497prep())
    suite.addTest(RegressionTestTicket5497a())
    suite.addTest(RegressionTestTicket5497b())
    suite.addTest(RegressionTestTicket5497c())
    suite.addTest(RegressionTestTicket5497d())
    suite.addTest(RegressionTestTicket5602())
    suite.addTest(RegressionTestTicket5687())
    suite.addTest(RegressionTestTicket5930())
    suite.addTest(RegressionTestTicket6048())
    suite.addTest(RegressionTestTicket6747())
    suite.addTest(RegressionTestTicket6879a())
    suite.addTest(RegressionTestTicket6879b())
    suite.addTest(RegressionTestTicket6912a())
    suite.addTest(RegressionTestTicket6912b())
    suite.addTest(RegressionTestTicket7821group())
    suite.addTest(RegressionTestTicket7821var())
    suite.addTest(RegressionTestTicket8247())
    suite.addTest(RegressionTestTicket8861())
    suite.addTest(RegressionTestTicket9084())
    suite.addTest(RegressionTestTicket9981())

    return suite


#--------------
# Multiproduct test cases
#--------------



def functionalSuite(suite=None):
    if not suite:
        from tests import functional
        suite = functional.functionalSuite()

    trac_functionalSuite(suite)

    return suite


if __name__ == '__main__':
    import unittest
    unittest.main(defaultTest='functionalSuite')
