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

from trac.ticket.tests.functional import *

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


# Ensure that overridden code will be loaded
def functionalSuite(suite=None):
    if not suite:
        import trac.tests.functional.testcases
        suite = trac.tests.functional.testcases.functionalSuite()

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


if __name__ == '__main__':
    unittest.main(defaultTest='functionalSuite')
