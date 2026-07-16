from django.db import models

from rxdjango.models import ReactiveModel


class Project(models.Model):
    """The routing dimension's namespace: a human-readable label for the
    `project_id` values tasks are grouped by. Not itself reactive -- these
    rows don't change in this example."""

    name = models.CharField(max_length=64)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name


class Task(ReactiveModel):
    """A task on a project's board. `project_id` is a plain column, not a
    Django `ForeignKey` -- deliberately, per ADR-0018's own framing
    ("like `db_index`": an explicit access path, not a relational
    constraint) and so the column-sugar `routing='project_id'` matches the
    same name on both the model attribute (`Router.publish`) and the
    queryset condition Django's query compiler resolves
    (`Router.subscribe`/bind-time introspection) -- a Django FK's `.name`
    ('project') and its `_id` attname ('project_id') differ, which the
    column sugar does not (yet) reconcile.

    A task's creation, and any move to a different `project_id`, is
    delivered live to every connection watching that project -- no rebind,
    unlike `static_list`'s Task.
    """

    name = models.CharField(max_length=64)
    status = models.CharField(max_length=16, default='open')
    priority = models.IntegerField(default=0)
    project_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name
