from django.contrib.auth.models import User, Group
from rest_framework import serializers
from trackers import models


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ('url', 'username', 'email', 'is_staff')


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ('url', 'name')


class TicketSerializer(serializers.ModelSerializer):
    api_url = serializers.SerializerMethodField()
    api_events_url = serializers.SerializerMethodField()

    class Meta:
        model = models.Ticket
        fields = '__all__'

    def get_api_url(self, obj):
        return self.context['request'].build_absolute_uri(obj.api_url())

    def get_api_events_url(self, obj):
        return self.context['request'].build_absolute_uri(obj.api_events_url())


class TicketFieldSerializer(serializers.ModelSerializer):
    api_url = serializers.SerializerMethodField()

    class Meta:
        model = models.TicketField
        fields = '__all__'

    def get_api_url(self, obj):
        return self.context['request'].build_absolute_uri(obj.api_url())


class ChangeEventSerializer(serializers.ModelSerializer):
    api_url = serializers.SerializerMethodField()
    api_ticket_url = serializers.SerializerMethodField()

    class Meta:
        model = models.ChangeEvent
        fields = '__all__'

    def get_api_url(self, obj):
        return self.context['request'].build_absolute_uri(obj.api_url())

    def get_api_ticket_url(self, obj):
        return self.context['request'].build_absolute_uri(obj.api_ticket_url())
