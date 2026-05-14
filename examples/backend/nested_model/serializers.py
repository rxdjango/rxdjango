from rest_framework import serializers
from nested_model.models import Company, User


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['name']


class UserSerializer(serializers.ModelSerializer):
    company = CompanySerializer()

    class Meta:
        model = User
        fields = ['name', 'company']
