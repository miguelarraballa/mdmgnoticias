from django.db import migrations


class Migration(migrations.Migration):
    """Set database-level DEFAULT '' on media columns for MySQL strict mode."""

    dependencies = [
        ('feeds', '0008_article_media_default'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "ALTER TABLE feeds_article MODIFY COLUMN media_url VARCHAR(1000) NOT NULL DEFAULT '';",
                "ALTER TABLE feeds_article MODIFY COLUMN media_type VARCHAR(100) NOT NULL DEFAULT '';",
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
