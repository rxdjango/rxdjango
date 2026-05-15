from rest_framework import serializers
from simple_model.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['name']
