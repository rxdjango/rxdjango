from django.db import models

from rxdjango.models import ReactiveModel


class Project(models.Model):
    """A board tasks are grouped under. Not itself reactive -- these
    rows don't change in this example."""

    name = models.CharField(max_length=64)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name


STATUS_CHOICES = [
    ('open', 'Open'),
    ('closed', 'Closed'),
]


class Task(ReactiveModel):
    """A task on a project's board. `project` is a plain Django
    `ForeignKey`; `routing='project_id'` and `routing='project'` name the
    same column, and a bound queryset may filter it as
    `.filter(project=obj)`, `.filter(project_id=5)`, or
    `.filter(project__id=5)` interchangeably.

    A task's creation, and any move to a different `project`, is
    delivered live to every connection watching that project -- no rebind.
    """

    name = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='open')
    priority = models.IntegerField(default=0)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name
