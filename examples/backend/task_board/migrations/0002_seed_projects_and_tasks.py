from django.db import migrations


PROJECTS = [
    dict(id=1, name='Website Redesign'),
    dict(id=2, name='Mobile App'),
]

TASKS = [
    dict(id=1, name='Draft homepage copy', status='open', priority=3, project_id=1),
    dict(id=2, name='Pick a color palette', status='open', priority=1, project_id=1),
    dict(id=3, name='Fix navbar overflow', status='open', priority=5, project_id=1),
    dict(id=4, name='Archive old landing page', status='closed', priority=0, project_id=1),
    dict(id=5, name='Wire up push notifications', status='open', priority=4, project_id=2),
    dict(id=6, name='Fix login crash on Android', status='open', priority=8, project_id=2),
]


def forwards(apps, schema):
    Project = apps.get_model('task_board', 'Project')
    Task = apps.get_model('task_board', 'Task')
    for fields in PROJECTS:
        Project.objects.create(**fields)
    for fields in TASKS:
        Task.objects.create(**fields)


def backwards(apps, schema):
    Task = apps.get_model('task_board', 'Task')
    Project = apps.get_model('task_board', 'Project')
    Task.objects.filter(id__in=[t['id'] for t in TASKS]).delete()
    Project.objects.filter(id__in=[p['id'] for p in PROJECTS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('task_board', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
