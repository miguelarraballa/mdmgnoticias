from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feeds', '0006_uploadedopml'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='media_url',
            field=models.URLField(blank=True, default='', max_length=1000),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='article',
            name='media_type',
            field=models.CharField(blank=True, default='', max_length=100),
            preserve_default=False,
        ),
    ]
