from django.db import migrations, models


class Migration(migrations.Migration):
    """Fix media_url and media_type columns to have DEFAULT '' on MySQL strict mode."""

    dependencies = [
        ('feeds', '0007_article_media'),
    ]

    operations = [
        migrations.AlterField(
            model_name='article',
            name='media_url',
            field=models.URLField(blank=True, default='', max_length=1000),
        ),
        migrations.AlterField(
            model_name='article',
            name='media_type',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
