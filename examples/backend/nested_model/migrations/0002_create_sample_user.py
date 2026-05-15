from django.db import migrations


def forwards(apps, schema):
    Company = apps.get_model('nested_model', 'Company')
    User = apps.get_model('nested_model', 'User')
    company = Company.objects.create(id=1, name='Lorem Ipsum Inc')
    User.objects.create(id=1, name='Registered User', company=company)


def backwards(apps, schema):
    User = apps.get_model('nested_model', 'User')
    Company = apps.get_model('nested_model', 'Company')
    User.objects.filter(id=1).delete()
    Company.objects.filter(id=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('nested_model', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards)
    ]
