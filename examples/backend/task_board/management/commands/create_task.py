"""A management-command writer that never imports `task_board.channels`
(routed-list-delivery task 2.4): if a saved Task still reaches its routing
dimension groups, that broadcast can only have come from the router
`rxdjango`'s `AppConfig.ready()` autodiscovered -- not from any import this
command performs itself.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from task_board.models import Task


class Command(BaseCommand):
    help = 'Create a Task under a project, from outside any web/channel context.'

    def add_arguments(self, parser):
        parser.add_argument('name')
        parser.add_argument('project_id', type=int)
        parser.add_argument('--priority', type=int, default=0)

    def handle(self, *args, **options):
        task = Task.objects.create(
            name=options['name'],
            project_id=options['project_id'],
            priority=options['priority'],
        )
        self.stdout.write(str(task.pk))
