from rxdjango import ContextChannel, action, rx

from .models import Task
from .serializers import TaskSerializer


class StaticQuerysetChannel(ContextChannel):
    """The static-queryset tier (ADR-0018/0019): a bare queryset assigned to a
    `many=True` field. `on_connect` binds `Task.objects.filter(status='open')
    .order_by('-priority', 'id')` -- no other declaration.

    Membership is entirely client-derived from there: `toggle_status` flips
    the residual (`status`) column an ordinary update frame re-evaluates;
    `bump_priority` moves a row through the client's own ordering
    comparator; `delete_task` tombstones a row out of the list. `add_task`
    deliberately does *not* appear until `rebind` runs again -- the static
    tier's one documented limitation (no live new-row delivery).
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
