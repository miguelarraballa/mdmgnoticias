import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import feedparser
import requests

_UA = 'Mozilla/5.0 (compatible; NewsFetcher/1.0)'
_SESSION = requests.Session()
_SESSION.headers['User-Agent'] = _UA


def fetch_raw(url):
    """
    Fetch a URL and return (bytes, content_type).

    Fixes XML encoding-declaration mismatches: if the HTTP response or BOM
    indicates UTF-8 but the <?xml?> prolog declares something else (a common
    mistake in Spanish news sites), we patch the declaration so feedparser
    does not reject the document.
    """
    resp = _SESSION.get(url, timeout=15, allow_redirects=True)
    resp.raise_for_status()
    content = resp.content
    content_type = resp.headers.get('content-type', '')

    # UTF-8 BOM takes priority; otherwise trust the HTTP charset header
    has_utf8_bom = content.startswith(b'\xef\xbb\xbf')
    http_enc = (resp.encoding or '').lower().replace('-', '')

    if has_utf8_bom:
        actual_enc = b'utf-8'
    elif http_enc == 'utf8':
        actual_enc = b'utf-8'
    else:
        actual_enc = None

    if actual_enc:
        content = re.sub(
            rb'(<\?xml[^>]+encoding=["\'])([^"\']+)(["\'])',
            rb'\g<1>' + actual_enc + rb'\g<3>',
            content,
            count=1,
        )

    return content, content_type


def is_opml(content_bytes, content_type='', url=''):
    """Return True if the content appears to be an OPML document."""
    if 'opml' in content_type.lower():
        return True
    if url and '.opml' in url.lower():
        return True
    # Peek at the XML root element
    try:
        stripped = content_bytes.lstrip()
        start = stripped.find(b'<')
        chunk = stripped[start:start + 512].lower()
        return b'<opml' in chunk
    except Exception:
        return False


def parse_opml(content_bytes):
    """
    Parse an OPML document and return a list of {'name': str, 'url': str} dicts
    for every RSS/Atom outline found.
    """
    feeds = []
    try:
        # Strip BOM and replace the XML encoding declaration with utf-8 so
        # ElementTree doesn't choke on malformed encoding names (e.g. "iso88591").
        data = content_bytes.lstrip(b'\xef\xbb\xbf')
        data = re.sub(
            rb'<\?xml[^>]+\?>',
            b'<?xml version="1.0" encoding="utf-8"?>',
            data,
            count=1,
        )
        root = ET.fromstring(data)
        for outline in root.iter('outline'):
            url = outline.get('xmlUrl') or outline.get('xmlurl') or outline.get('xmlURL')
            if url:
                name = (
                    outline.get('title')
                    or outline.get('text')
                    or url
                )
                html_url = (
                    outline.get('htmlUrl') or outline.get('htmlurl') or outline.get('htmlURL') or ''
                )
                feeds.append({'name': name.strip(), 'url': url.strip(), 'html_url': html_url.strip()})
    except Exception:
        pass
    return feeds


def parse_feed(content, url):
    """
    Parse RSS/Atom bytes using progressively more lenient strategies.

    1. feedparser on our encoding-fixed bytes (fast path, handles most feeds)
    2. lxml recover=True → re-serialize → feedparser (fixes mismatched tags,
       unclosed elements, etc.)
    3. feedparser fetches the URL directly with its own HTTP client (last resort;
       bypasses our preprocessing but has its own detection logic)

    Always returns a feedparser result object.
    """
    parsed = feedparser.parse(content)
    if not (parsed.get('bozo') and len(parsed.entries) == 0):
        return parsed

    # Attempt 2: lxml with XML recovery
    try:
        from lxml import etree
        lxml_parser = etree.XMLParser(recover=True, remove_comments=True, encoding='utf-8')
        data = content.lstrip(b'\xef\xbb\xbf')
        tree = etree.fromstring(data, lxml_parser)
        recovered = etree.tostring(tree, xml_declaration=True, encoding='utf-8')
        parsed2 = feedparser.parse(recovered)
        if len(parsed2.entries) > 0:
            return parsed2
    except Exception:
        pass

    # Attempt 3: let feedparser handle HTTP itself (with hard timeout)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(feedparser.parse, url)
            parsed3 = future.result(timeout=10)
        if len(parsed3.entries) > 0:
            return parsed3
    except (FuturesTimeoutError, Exception):
        pass

    return parsed  # return original with bozo info intact


def find_favicon(parsed_feed, feed_url):
    """
    Try to find a logo/favicon for a feed in this order:
    1. RSS <image> or Atom <icon>/<logo> fields
    2. /favicon.ico on the domain
    3. <link rel="icon"> in the homepage HTML
    """
    feed_meta = getattr(parsed_feed, 'feed', {})

    image = feed_meta.get('image') or {}
    url = image.get('href') or image.get('url')
    if url:
        return url

    for field in ('icon', 'logo'):
        url = feed_meta.get(field)
        if url:
            return url

    # /favicon.ico
    try:
        parsed = urlparse(feed_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        favicon_url = f"{base}/favicon.ico"
        req = urllib.request.Request(favicon_url, headers={'User-Agent': _UA})
        with urllib.request.urlopen(req, timeout=5) as r:
            ct = r.headers.get('content-type', '')
            if r.status == 200 and ('image' in ct or ct == ''):
                return favicon_url
    except Exception:
        pass

    # <link rel="icon"> in homepage
    try:
        parsed = urlparse(feed_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        req = urllib.request.Request(base, headers={'User-Agent': _UA})
        with urllib.request.urlopen(req, timeout=6) as r:
            chunk = r.read(16384).decode('utf-8', errors='ignore')

        patterns = [
            r'<link[^>]+rel=["\'][^"\']*icon[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
            r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\'][^"\']*icon[^"\']*["\']',
        ]
        for pat in patterns:
            m = re.search(pat, chunk, re.I)
            if m:
                href = m.group(1)
                return urljoin(base, href)
    except Exception:
        pass

    return ''
