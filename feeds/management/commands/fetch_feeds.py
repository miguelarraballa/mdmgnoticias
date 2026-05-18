import hashlib
import html
import re
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from feeds.models import Article, Feed, SiteConfig
from feeds.utils import fetch_raw, find_favicon, is_opml, parse_feed, parse_opml


def _strip_tags(text):
    """Strip HTML tags from a string."""
    return re.sub(r'<[^>]+>', '', text or '')


def _clean(text):
    """Strip HTML tags and unescape HTML entities from a string."""
    return html.unescape(_strip_tags(text)).strip()


def _get_image(entry):
    """Return the URL of the first image associated with a feed entry, or ''."""
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url', '')
    if hasattr(entry, 'media_content') and entry.media_content:
        for mc in entry.media_content:
            if mc.get('type', '').startswith('image/'):
                return mc.get('url', '')
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/'):
                return enc.get('href', '')
    return ''


def _get_media(entry):
    """Return (url, mime_type) for the first audio or video enclosure, or ('', '')."""
    _AUDIO_EXTS = ('.mp3', '.ogg', '.wav', '.aac', '.opus', '.flac', '.m4a')
    _VIDEO_EXTS = ('.mp4', '.webm', '.ogv', '.m4v', '.mov', '.avi')

    def _is_av(mime, url):
        if mime.startswith('audio/') or mime.startswith('video/'):
            return True
        u = url.lower()
        return any(u.endswith(e) for e in _AUDIO_EXTS + _VIDEO_EXTS)

    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            mime = enc.get('type', '')
            url = enc.get('href', '') or enc.get('url', '')
            if url and _is_av(mime, url):
                return url, mime

    if hasattr(entry, 'media_content') and entry.media_content:
        for mc in entry.media_content:
            mime = mc.get('type', '')
            url = mc.get('url', '')
            if url and _is_av(mime, url):
                return url, mime

    return '', ''


def _parse_date(entry):
    """Parse the published/updated date from a feed entry, falling back to now."""
    dt = entry.get('published_parsed') or entry.get('updated_parsed')
    if dt:
        import calendar
        from datetime import datetime, timezone as dt_tz
        try:
            return datetime.fromtimestamp(calendar.timegm(dt), tz=dt_tz.utc)
        except Exception:
            pass
    return timezone.now()


def _entry_text_for_filter(entry):
    """Concatenate all searchable text fields of an entry for keyword matching."""
    parts = [
        entry.get('title', ''),
        entry.get('summary', ''),
        entry.get('description', ''),
    ]
    for tag in entry.get('tags', []):
        parts.append(tag.get('term', ''))
        parts.append(tag.get('label', ''))
    return ' '.join(filter(None, parts)).lower()


def _is_blocked(entry, blocked_keywords):
    """Return True if the entry contains any of the feed's blocked keywords."""
    if not blocked_keywords:
        return False
    text = _entry_text_for_filter(entry)
    return any(kw in text for kw in blocked_keywords)


def _fetch_and_parse(url):
    """
    Fetch a feed URL and return (parsed, opml_entries, error).
    Exactly one of parsed/opml_entries will be non-None on success.
    """
    try:
        content, content_type = fetch_raw(url)
    except Exception as e:
        return None, None, str(e)

    if is_opml(content, content_type, url):
        entries = parse_opml(content)
        return None, entries, None

    parsed = parse_feed(content, url)
    return parsed, None, None


def _process_feed(feed, cutoff=None):
    """Fetch and store new articles for a single feed. Returns (new_count, blocked_count)."""
    blocked_keywords = feed.get_blocked_keywords()
    parsed, opml_entries, error = _fetch_and_parse(feed.url)

    if error or opml_entries is not None:
        return 0, 0

    if feed.medio and not feed.medio.favicon_url:
        favicon = find_favicon(parsed, feed.url)
        if favicon:
            feed.medio.favicon_url = favicon
            feed.medio.save(update_fields=['favicon_url'])

    new_count = 0
    blocked_count = 0
    for entry in parsed.entries:
        guid = entry.get('id') or entry.get('link', '')
        if not guid:
            continue
        if len(guid) > 255:
            guid = 'sha256:' + hashlib.sha256(guid.encode()).hexdigest()

        if _is_blocked(entry, blocked_keywords):
            blocked_count += 1
            continue

        title = _clean(entry.get('title', '(sin título)'))
        link = entry.get('link', '')
        summary = _clean(
            entry.get('summary', '') or
            entry.get('description', '') or
            (entry.get('content', [{}])[0].get('value', '')
             if hasattr(entry.get('content', None), '__iter__') else '')
        )
        published_at = _parse_date(entry)
        if cutoff and published_at < cutoff:
            continue

        image_url = _get_image(entry)
        media_url, media_type = _get_media(entry)

        _, created = Article.objects.get_or_create(
            guid=guid,
            defaults={
                'feed': feed,
                'title': title[:500],
                'summary': summary,
                'link': link[:1000],
                'published_at': published_at,
                'image_url': image_url[:1000],
                'media_url': media_url[:1000],
                'media_type': media_type[:100],
            }
        )
        if created:
            new_count += 1

    feed.last_fetched = timezone.now()
    feed.save(update_fields=['last_fetched'])
    return new_count, blocked_count


def fetch_feed_batch(offset=0, batch_size=5):
    """
    Process a batch of active feeds starting at `offset`.
    Returns a dict with progress info suitable for JSON responses.
    """
    config = SiteConfig.get()
    cutoff = timezone.now() - timedelta(days=config.articles_retention_days)

    feeds = list(Feed.objects.filter(is_active=True).order_by('id'))
    total = len(feeds)
    batch = feeds[offset:offset + batch_size]
    new_articles = 0
    blocked = 0

    for feed in batch:
        n, b = _process_feed(feed, cutoff=cutoff)
        new_articles += n
        blocked += b

    next_offset = offset + len(batch)
    return {
        'total': total,
        'processed': next_offset,
        'next_offset': next_offset,
        'done': next_offset >= total,
        'new_articles': new_articles,
        'blocked': blocked,
    }


class Command(BaseCommand):
    help = 'Fetch articles from all active feeds'

    def add_arguments(self, parser):
        """Register optional --batch-size and --offset CLI arguments."""
        parser.add_argument('--batch-size', type=int, default=0,
                            help='Process only N feeds (0 = all)')
        parser.add_argument('--offset', type=int, default=0,
                            help='Start from this feed index')

    def handle(self, *args, **options):
        """Fetch all active feeds, skipping articles older than the retention window."""
        batch_size = options['batch_size']
        offset = options['offset']

        config = SiteConfig.get()
        cutoff = timezone.now() - timedelta(days=config.articles_retention_days)
        self.stdout.write(f'Descartando artículos anteriores a {cutoff.strftime("%Y-%m-%d")} ({config.articles_retention_days} días)')

        feeds = list(Feed.objects.filter(is_active=True).order_by('id'))
        if batch_size:
            feeds = feeds[offset:offset + batch_size]
        elif offset:
            feeds = feeds[offset:]

        total_new = 0
        total_blocked = 0

        for feed in feeds:
            self.stdout.write(f'Fetching: {feed.name}')
            parsed, opml_entries, error = _fetch_and_parse(feed.url)

            if error:
                self.stderr.write(f'  Error: {error}')
                continue

            if opml_entries is not None:
                self.stdout.write(f'  → OPML con {len(opml_entries)} feeds (importación manual)')
                continue

            if feed.medio and not feed.medio.favicon_url:
                favicon = find_favicon(parsed, feed.url)
                if favicon:
                    feed.medio.favicon_url = favicon
                    feed.medio.save(update_fields=['favicon_url'])
                    self.stdout.write(f'  → logo detectado para {feed.medio.name}: {favicon}')

            new_count, blocked_count = 0, 0
            blocked_keywords = feed.get_blocked_keywords()
            for entry in parsed.entries:
                guid = entry.get('id') or entry.get('link', '')
                if not guid:
                    continue
                if len(guid) > 255:
                    guid = 'sha256:' + hashlib.sha256(guid.encode()).hexdigest()

                if _is_blocked(entry, blocked_keywords):
                    blocked_count += 1
                    continue

                title = _clean(entry.get('title', '(sin título)'))
                link = entry.get('link', '')
                summary = _clean(
                    entry.get('summary', '') or
                    entry.get('description', '') or
                    (entry.get('content', [{}])[0].get('value', '')
                     if hasattr(entry.get('content', None), '__iter__') else '')
                )
                published_at = _parse_date(entry)
                if published_at < cutoff:
                    continue

                image_url = _get_image(entry)
                media_url, media_type = _get_media(entry)

                _, created = Article.objects.get_or_create(
                    guid=guid,
                    defaults={
                        'feed': feed,
                        'title': title[:500],
                        'summary': summary,
                        'link': link[:1000],
                        'published_at': published_at,
                        'image_url': image_url[:1000],
                        'media_url': media_url[:1000],
                        'media_type': media_type[:100],
                    }
                )
                if created:
                    new_count += 1

            feed.last_fetched = timezone.now()
            feed.save(update_fields=['last_fetched'])
            msg = f'  → {new_count} nuevos artículos'
            if blocked_count:
                msg += f' · {blocked_count} bloqueados'
            self.stdout.write(msg)
            total_new += new_count
            total_blocked += blocked_count

        self.stdout.write(self.style.SUCCESS(
            f'Total nuevos: {total_new} · Total bloqueados: {total_blocked}'
        ))
