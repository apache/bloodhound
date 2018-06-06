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

import difflib
import functools
import logging
import uuid

from django.db import models

logger = logging.getLogger(__name__)

class ModelCommon(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        abstract = True

class Ticket(ModelCommon):

    def last_update(self):
        last_event = self.changeevent_set.order_by('created').last()
        return self.created if last_event is None else last_event.created

    def add_field_event(self, field, newvalue):
        current_lines = self.get_field_value(field).splitlines(keepends=True)
        replace_lines = newvalue.splitlines(keepends=True)
        result = '\n'.join(difflib.ndiff(current_lines, replace_lines))

        tfield, created = TicketField.objects.get_or_create(name=field)
        c = ChangeEvent(ticket=self, field=tfield, diff=result)
        c.save()

    def get_field_value(self, field):
        try:
            tfield = TicketField.objects.get(name=field)
        except TicketField.DoesNotExist as e:
            return ''

        event = self.changeevent_set.filter(field=tfield).order_by('created').last()
        return '' if event is None else event.value()


class TicketField(ModelCommon):
    name = models.CharField(max_length=32)

class ChangeEvent(ModelCommon):
    ticket = models.ForeignKey(Ticket, models.CASCADE, editable=False, null=False)
    field = models.ForeignKey(TicketField, models.CASCADE, editable=False, null=False)
    diff = models.TextField(editable=False)

    def value(self, which=2):
        return ''.join(difflib.restore(self.diff.splitlines(keepends=True), which)).strip()

    old_value = functools.partialmethod(value, which=1)

    def __str__(self):
        return "Change to: {}; Field: {}; Diff: {}".format(
            self.ticket, self.field, self.diff)

