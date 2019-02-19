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

from django.contrib.auth.models import User, Group
from django.http import HttpResponse
from rest_framework import viewsets
from . import serializers
from . import models

from rest_framework_swagger.views import get_swagger_view

schema_view = get_swagger_view(title='Bloodhound Core API')


def home(request):
    return HttpResponse('<html><title>Bloodhound Trackers</title></html>')


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = serializers.GroupSerializer


class TicketFieldViewSet(viewsets.ModelViewSet):
    queryset = models.TicketField.objects.all()
    serializer_class = serializers.TicketFieldSerializer


class TicketViewSet(viewsets.ModelViewSet):
    queryset = models.Ticket.objects.all()
    serializer_class = serializers.TicketSerializer


class ChangeEventViewSet(viewsets.ModelViewSet):
    queryset = models.ChangeEvent.objects.all()
    serializer_class = serializers.ChangeEventSerializer
