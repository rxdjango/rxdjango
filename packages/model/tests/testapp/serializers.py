from rest_framework import serializers

from .models import Badge, Company, Employee, Skill, Task, Team


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ['id', 'code']


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name']


class EmployeeSerializer(serializers.ModelSerializer):
    skills = SkillSerializer(many=True)
    badge = BadgeSerializer()

    class Meta:
        model = Employee
        fields = ['id', 'name', 'skills', 'badge']


class TeamSerializer(serializers.ModelSerializer):
    employees = EmployeeSerializer(many=True)

    class Meta:
        model = Team
        fields = ['id', 'name', 'employees']


class CompanySerializer(serializers.ModelSerializer):
    teams = TeamSerializer(many=True)

    class Meta:
        model = Company
        fields = ['id', 'name', 'teams']


class TeamNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ['id', 'name']


class EmployeeWithTeamSerializer(serializers.ModelSerializer):
    """Forward (nullable) FK nesting."""
    team = TeamNameSerializer()

    class Meta:
        model = Employee
        fields = ['id', 'name', 'team']


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['id', 'name', 'status', 'priority', 'created_at']
