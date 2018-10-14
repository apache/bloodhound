from rest_framework import serializers
from trackers.models import Ticket, TicketField, ChangeEvent


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = '__all__'


class TicketFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketField
        fields = '__all__'


class ChangeEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChangeEvent
        fields = '__all__'
