"""Models exercising every relation shape StateModel claims to handle:
forward FK (nullable), reverse FK (many), M2M, reverse one-to-one, and
two-level nesting. Explicit ordering keeps serialized layers deterministic.
"""
from django.db import models

from rxdjango.models import ReactiveModel


class Company(models.Model):
    name = models.CharField(max_length=64)

    class Meta:
        ordering = ['id']


class Team(models.Model):
    name = models.CharField(max_length=64)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='teams')

    class Meta:
        ordering = ['id']


class Employee(models.Model):
    name = models.CharField(max_length=64)
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL, related_name='employees')

    class Meta:
        ordering = ['id']


class Skill(models.Model):
    name = models.CharField(max_length=64)
    employees = models.ManyToManyField(Employee, related_name='skills')

    class Meta:
        ordering = ['id']


class Badge(models.Model):
    code = models.CharField(max_length=16)
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='badge')

    class Meta:
        ordering = ['id']


class Task(ReactiveModel):
    """Reactive top-level model for `many=True` list-field tests (the
    static-queryset-lists change): a real broadcast group per row, a
    residual (`status`) column, and an ordering column (`priority`)."""
    name = models.CharField(max_length=64)
    status = models.CharField(max_length=16, default='open')
    priority = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
