from django.db import models

from rxdjango.models import ReactiveModel


class Task(ReactiveModel):
    """A task on a shared board. `status` (plain 'open'/'closed' strings, no
    `choices=` -- that maps to a DRF `ChoiceField`, which the TS generator
    doesn't special-case yet, an unrelated pre-existing gap not worth
    demonstrating here) is the residual column the channel's queryset
    filters on; `priority` is its ordering column."""

    name = models.CharField(max_length=64)
    status = models.CharField(max_length=16, default='open')
    priority = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name
