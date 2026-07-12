import threading
import time

from rxdjango import ContextChannel, rx, action
from .models import Project, Task
from .serializers import TaskSerializer


class ReactiveModelChannel(ContextChannel):

    task = rx.model(TaskSerializer())

    async def on_connect(self):
        self.task = await Task.objects.select_related('project').aget(id=1)

    @action
    async def modify_project(self, name: str, delay: int):
        project_id = self.task.project.id

        def _update():
            time.sleep(delay)
            project = Project.objects.get(id=project_id)
            project.name = name
            project.save()

        threading.Thread(target=_update, daemon=True).start()
