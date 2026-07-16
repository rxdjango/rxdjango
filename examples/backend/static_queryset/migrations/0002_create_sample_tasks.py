from django.db import migrations


TASKS = [
    dict(id=1, name='Ship the release notes', status='open', priority=3),
    dict(id=2, name='Review pull request', status='open', priority=1),
    dict(id=3, name='Fix flaky test', status='open', priority=5),
    dict(id=4, name='Update dependencies', status='closed', priority=0),
]


def forwards(apps, schema):
    Task = apps.get_model('static_queryset', 'Task')
    for fields in TASKS:
        Task.objects.create(**fields)


def backwards(apps, schema):
    Task = apps.get_model('static_queryset', 'Task')
    Task.objects.filter(id__in=[t['id'] for t in TASKS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('static_queryset', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards)
    ]
