from rest_framework import serializers

from .models import VersionedCounter


class VersionedCounterSerializer(serializers.ModelSerializer):
    class Meta:
        model = VersionedCounter
        fields = ['id', 'value']
