from django.db import models

from rxdjango.models import ReactiveModel


class Project(ReactiveModel):
    name = models.CharField(max_length=64)


class Task(ReactiveModel):
    name = models.CharField(max_length=64)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
