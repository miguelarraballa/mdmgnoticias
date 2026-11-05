from django.core.management.base import BaseCommand

from feeds.tagging import TaggerError, is_configured, tag_pending_articles


class Command(BaseCommand):
    help = 'Assign tags to recent untagged articles using the configured AI API'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=25,
                            help='Articles sent per API request')
        parser.add_argument('--max-batches', type=int, default=8,
                            help='Maximum API requests in this run')

    def handle(self, *args, **options):
        if not is_configured():
            self.stdout.write('Etiquetado desactivado: faltan TAGGER_API_KEY y/o TAGGER_MODEL')
            return
        try:
            count = tag_pending_articles(options['batch_size'], options['max_batches'])
        except TaggerError as exc:
            self.stderr.write(f'Etiquetado interrumpido: {exc}')
            return
        self.stdout.write(self.style.SUCCESS(f'Artículos etiquetados: {count}'))
