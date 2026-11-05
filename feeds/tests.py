import json
from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from . import tagging
from .models import Article, Feed, Tag


def api_response(entries, status=200):
    response = mock.Mock(status_code=status, text='error')
    response.json.return_value = {
        'choices': [{'message': {'content': json.dumps({'articles': entries})}}]
    }
    return response


@override_settings(TAGGER_API_KEY='key', TAGGER_MODEL='model')
class TaggingTests(TestCase):
    def setUp(self):
        self.feed = Feed.objects.create(name='F', url='https://example.com/rss')

    def make_article(self, guid, age_days=0):
        return Article.objects.create(
            feed=self.feed, title=guid, link='https://example.com/' + guid, guid=guid,
            published_at=timezone.now() - timedelta(days=age_days),
        )

    @mock.patch('feeds.tagging.requests.post')
    def test_tags_saved_and_variants_unified(self, post):
        first, second = self.make_article('a'), self.make_article('b')
        post.return_value = api_response([
            {'n': 1, 'tags': ['#Pedro Sánchez', 'PSOE']},
            {'n': 2, 'tags': ['pedro sanchez']},
        ])
        self.assertEqual(tagging.tag_pending_articles(max_batches=1), 2)
        self.assertEqual(Tag.objects.filter(slug='pedro-sanchez').count(), 1)
        tag = Tag.objects.get(slug='pedro-sanchez')
        self.assertEqual(tag.name, 'Pedro Sánchez')
        self.assertCountEqual(tag.articles.all(), [first, second])

    @mock.patch('feeds.tagging.requests.post')
    def test_unusable_tags_dropped_and_article_not_retried(self, post):
        article = self.make_article('a')
        post.return_value = api_response([
            {'n': 1, 'tags': ['x' * 200, 7, 'Válido', '!!!']},
            {'n': 99, 'tags': ['Fuera de lote']},
        ])
        tagging.tag_pending_articles(max_batches=1)
        article.refresh_from_db()
        self.assertEqual([t.name for t in article.tags.all()], ['Válido'])
        self.assertIsNotNone(article.tagged_at)
        self.assertFalse(Tag.objects.filter(name='Fuera de lote').exists())

    @mock.patch('feeds.tagging.requests.post')
    def test_api_error_keeps_articles_pending(self, post):
        article = self.make_article('a')
        post.return_value = api_response([], status=429)
        with self.assertRaises(tagging.TaggerError):
            tagging.tag_pending_articles(max_batches=1)
        article.refresh_from_db()
        self.assertIsNone(article.tagged_at)

    @mock.patch('feeds.tagging.time.sleep')
    @mock.patch('feeds.tagging.requests.post')
    def test_overloaded_model_is_retried(self, post, _sleep):
        article = self.make_article('a')
        post.side_effect = [api_response([], status=503), api_response([{'n': 1, 'tags': ['Gaza']}])]
        self.assertEqual(tagging.tag_pending_articles(max_batches=1), 1)
        self.assertEqual(article.tags.get().name, 'Gaza')

    @mock.patch('feeds.tagging.time.sleep')
    @mock.patch('feeds.tagging.requests.post')
    def test_rate_limit_is_not_retried(self, post, _sleep):
        self.make_article('a')
        post.return_value = api_response([], status=429)
        with self.assertRaises(tagging.TaggerError):
            tagging.tag_pending_articles(max_batches=1)
        self.assertEqual(post.call_count, 1)

    @mock.patch('feeds.tagging.requests.post')
    def test_malformed_answer_keeps_articles_pending(self, post):
        article = self.make_article('a')
        response = mock.Mock(status_code=200)
        response.json.return_value = {'choices': [{'message': {'content': 'no es json'}}]}
        post.return_value = response
        with self.assertRaises(tagging.TaggerError):
            tagging.tag_pending_articles(max_batches=1)
        article.refresh_from_db()
        self.assertIsNone(article.tagged_at)

    @mock.patch('feeds.tagging.requests.post')
    def test_old_articles_not_sent(self, post):
        self.make_article('old', age_days=tagging.MAX_ARTICLE_AGE_DAYS + 1)
        self.assertEqual(tagging.tag_pending_articles(), 0)
        post.assert_not_called()

    def test_tag_page_lists_only_its_articles(self):
        tagged, other = self.make_article('tagged'), self.make_article('other')
        tag = Tag.for_name('Gaza')
        tagged.tags.add(tag)
        response = self.client.get(f'/t/{tag.slug}/', secure=True)
        self.assertContains(response, '/a/%d/' % tagged.pk)
        self.assertNotContains(response, '/a/%d/' % other.pk)
        self.assertContains(response, 'href="/t/gaza/"')
        self.assertEqual(self.client.get('/t/nope/', secure=True).status_code, 404)

    def test_trending_counts_recent_articles_only(self):
        popular, rare, stale, future = (Tag.for_name(n) for n in ('Popular', 'Rara', 'Vieja', 'Futura'))
        for guid in ('a', 'b'):
            self.make_article(guid).tags.add(popular)
        self.make_article('c').tags.add(rare)
        self.make_article('old', age_days=5).tags.add(stale)
        self.make_article('next', age_days=-5).tags.add(future)
        self.assertEqual([(t.name, t.uses) for t in Tag.trending()], [('Popular', 2), ('Rara', 1)])
        self.assertEqual(len(Tag.trending(limit=1)), 1)

    def test_trending_dropdown_rendered(self):
        self.make_article('a').tags.add(Tag.for_name('Gaza'))
        response = self.client.get('/', secure=True)
        self.assertContains(response, 'id="trending-select"')
        self.assertContains(response, '<option value="/t/gaza/" >#Gaza (1)</option>', html=True)

    def test_new_count_filters_by_tag(self):
        tagged, _other = self.make_article('tagged'), self.make_article('other')
        tag = Tag.for_name('Gaza')
        tagged.tags.add(tag)
        response = self.client.get('/api/new-count/', {'after': 0, 'tag': 'gaza'}, secure=True)
        self.assertEqual(response.json()['count'], 1)
