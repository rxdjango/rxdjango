from django.db import models

from rxdjango.models import ReactiveModel


class Task(ReactiveModel):
    """A task on a shared board: the channel's queryset filters on
    `status` and orders by `priority`."""

    name = models.CharField(max_length=64)
    status = models.CharField(max_length=16, default='open')
    priority = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name
