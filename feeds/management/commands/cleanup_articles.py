from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from feeds.models import Article, SiteConfig


class Command(BaseCommand):
    help = 'Delete articles older than the configured retention period'

    def handle(self, *args, **options):
        """Delete all articles whose published_at is older than articles_retention_days."""
        config = SiteConfig.get()
        days = config.articles_retention_days
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = Article.objects.filter(published_at__lt=cutoff).delete()
        self.stdout.write(
            self.style.SUCCESS(f'Deleted {deleted} articles older than {days} days')
        )
