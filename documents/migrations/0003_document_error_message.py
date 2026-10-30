from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0002_documentchunk_embedding'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='error_message',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
