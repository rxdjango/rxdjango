from rxdjango import ContextChannel, action, rx

from .models import Task
from .serializers import TaskSerializer


class StaticQuerysetChannel(ContextChannel):
    """A bare queryset assigned to a `many=True` field. `on_connect` binds
    `Task.objects.filter(status='open').order_by('-priority', 'id')` -- no
    other declaration.

    The client keeps the list correct from there: `toggle_status` flips a
    task out of (or back into) the list, `bump_priority` re-sorts it, and
    `delete_task` removes it. `add_task` deliberately does *not* appear
    until `rebind` runs again -- new rows arrive live only on a routed
    list (see `task_board`).
    """

    tasks = rx.model(TaskSerializer(many=True))

    async def on_connect(self):
        self._bind()

    def _bind(self):
        self.tasks = Task.objects.filter(status='open').order_by('-priority', 'id')

    @action
    async def rebind(self):
        self._bind()

    @action
    async def toggle_status(self, task_id: int):
        task = await Task.objects.aget(id=task_id)
        task.status = 'closed' if task.status == 'open' else 'open'
        await task.asave()

    @action
    async def bump_priority(self, task_id: int, delta: int):
        task = await Task.objects.aget(id=task_id)
        task.priority += delta
        await task.asave()

    @action
    async def delete_task(self, task_id: int):
        task = await Task.objects.aget(id=task_id)
        await task.adelete()

    @action
    async def add_task(self, name: str, priority: int):
        await Task.objects.acreate(name=name, status='open', priority=priority)
