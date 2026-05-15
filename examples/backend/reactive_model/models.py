from django.db import models


class Project(models.Model):
    name = models.CharField(max_length=64)


class Task(models.Model):
    name = models.CharField(max_length=64)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
