from django.db import migrations


def forwards(apps, schema):
    Project = apps.get_model('reactive_model', 'Project')
    Task = apps.get_model('reactive_model', 'Task')
    project = Project.objects.create(id=1, name='My Project')
    Task.objects.create(id=1, name='First Task', project=project)


def backwards(apps, schema):
    Task = apps.get_model('reactive_model', 'Task')
    Project = apps.get_model('reactive_model', 'Project')
    Task.objects.filter(id=1).delete()
    Project.objects.filter(id=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('reactive_model', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards)
    ]
