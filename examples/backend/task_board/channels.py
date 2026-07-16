from rxdjango import ContextChannel, action, rx

from .models import Task
from .serializers import TaskSerializer


class TaskBoardChannel(ContextChannel):
    """`tasks` declares `routing='project_id'`, so the list is *live* -- a
    task created under, or moved into, the selected project appears with
    no rebind, and a task moved out disappears just as immediately.
    Contrast with `static_queryset.StaticQuerysetChannel`, whose `tasks`
    field has no `routing=` and only sees new rows when `rebind()` runs.

    `select_project` is a client action rather than a URL parameter: the
    channel connects with no project chosen (`tasks` stays `null`), and the
    client picks one after connecting -- letting one demo page open several
    independently-routed boards over one static endpoint.
    """

    tasks = rx.model(TaskSerializer(many=True), routing='project_id')

    async def on_connect(self):
        self.project_id: int | None = None

    @action
    async def select_project(self, project_id: int):
        self.project_id = project_id
        self._bind()

    def _bind(self):
        self.tasks = Task.objects.filter(
            project_id=self.project_id, status='open',
        ).order_by('-priority', 'id')

    @action
    async def add_task(self, name: str, priority: int = 0):
        # Appears live, at its ordered position, on every connection
        # watching this project.
        await Task.objects.acreate(
            name=name, status='open', priority=priority, project_id=self.project_id,
        )

    @action
    async def move_task(self, task_id: int, project_id: int):
        # The task leaves this connection's list live, and appears live on
        # any connection watching the destination project.
        task = await Task.objects.aget(id=task_id)
        task.project_id = project_id
        await task.asave()

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
