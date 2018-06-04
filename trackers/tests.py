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

from django.http import HttpRequest
from django.test import TestCase
from django.urls import resolve
from trackers.views import home


class HomePageTest(TestCase):
    def test_root_url_resolves_to_home_page_view(self):
        found = resolve('/')
        self.assertEqual(found.func, home)

    def test_home_page_returns_expected_html(self):
        request = HttpRequest()
        response = home(request)

        self.assertTrue(response.content.startswith(b'<html>'))
        self.assertIn(b'<title>Bloodhound Trackers</title>', response.content)
        self.assertTrue(response.content.endswith(b'</html>'))


from trackers.models import Ticket

class TicketModelTest(TestCase):
    def test_last_update_on_create_returns_created_date(self):
        t = Ticket()
        t.save()
        self.assertEqual(t.created, t.last_update())

    def test_last_update_returns_last_change_date(self):
        # test may be safer with a fixture with an existing ticket to check
        t = Ticket()
        t.save()
        t.add_field_event('summary', "this is the summary")
        self.assertNotEqual(t.created, t.last_update())

    def test_ticket_creation(self):
        # Currently simple but may need updates for required fields
        pre_count = Ticket.objects.count()
        t = Ticket()
        t.save()
        self.assertEqual(pre_count + 1, Ticket.objects.count())

    def test_ticket_add_field_event(self):
        field = 'summary'
        field_value = "this is the summary"

        t = Ticket()
        t.save()
        t.add_field_event(field, field_value)

        self.assertEqual(t.get_field_value(field), field_value)

    def test_ticket_add_two_single_line_field_events_same_field(self):
        field = 'summary'
        first_field_value = "this is the summary"
        second_field_value = "this is the replacement summary"

        t = Ticket()
        t.save()
        t.add_field_event(field, first_field_value)
        t.add_field_event(field, second_field_value)

        self.assertEqual(t.get_field_value(field), second_field_value)

    def test_ticket_add_two_multiline_field_events_same_field(self):
        field = 'summary'
        first_field_value = "this is the summary\nwith multiple lines"
        second_field_value = "this is the replacement summary\nwith multiple lines"

        t = Ticket()
        t.save()
        t.add_field_event(field, first_field_value)
        t.add_field_event(field, second_field_value)

        self.assertEqual(t.get_field_value(field), second_field_value)

