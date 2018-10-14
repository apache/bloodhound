from rest_framework import serializers
from trackers.models import Ticket


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = '__all__'

class ChangeEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChangeEvent
        fields = '__all__'
