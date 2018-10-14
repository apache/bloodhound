from rest_framework import serializers
from trackers import models


class TicketSerializer(serializers.ModelSerializer):
    api_url = serializers.SerializerMethodField()

    class Meta:
        model = models.Ticket
        fields = '__all__'

    def get_api_url(self, obj):
        return self.context['request'].build_absolute_uri(obj.api_url())


class TicketFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TicketField
        fields = '__all__'


class ChangeEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ChangeEvent
        fields = '__all__'
