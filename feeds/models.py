import uuid as _uuid

from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not set."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Medio(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    favicon_url = models.URLField(blank=True)

    class Meta:
        verbose_name_plural = 'medios'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not set."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Feed(models.Model):
    name = models.CharField(max_length=200)
    url = models.URLField(unique=True)
    medio = models.ForeignKey(
        Medio, on_delete=models.SET_NULL, null=True, blank=True, related_name='feeds'
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='feeds'
    )
    is_active = models.BooleanField(default=True)
    last_fetched = models.DateTimeField(null=True, blank=True)
    blocked_keywords = models.TextField(
        blank=True,
        help_text='Palabras separadas por comas. Se excluirán artículos que las contengan en etiquetas, título o resumen.'
    )

    def get_blocked_keywords(self):
        """Return a list of lowercased, stripped keywords from the blocked_keywords field."""
        return [kw.strip().lower() for kw in self.blocked_keywords.split(',') if kw.strip()]

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class SiteConfig(models.Model):
    THEME_CHOICES = [('light', 'Claro'), ('dark', 'Oscuro'), ('system', 'Sistema (según dispositivo)')]
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='system')
    articles_retention_days = models.PositiveIntegerField(default=15)

    class Meta:
        verbose_name = 'Configuración del sitio'

    @classmethod
    def get(cls):
        """Return the singleton SiteConfig row, creating it with defaults if absent."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        """Force pk=1 to maintain singleton behaviour."""
        self.pk = 1
        super().save(*args, **kwargs)


class UploadedOPML(models.Model):
    id = models.UUIDField(primary_key=True, default=_uuid.uuid4, editable=False)
    filename = models.CharField(max_length=255)
    content = models.TextField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.filename


class Article(models.Model):
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name='articles')
    title = models.CharField(max_length=500)
    summary = models.TextField(blank=True)
    link = models.URLField(max_length=1000)
    guid = models.CharField(max_length=255, unique=True)
    published_at = models.DateTimeField()
    image_url = models.URLField(max_length=1000, blank=True)
    media_url = models.URLField(max_length=1000, blank=True, default='')
    media_type = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        return self.title

    _AUDIO_EXTS = ('.mp3', '.ogg', '.wav', '.aac', '.opus', '.flac', '.m4a')
    _VIDEO_EXTS = ('.mp4', '.webm', '.ogv', '.m4v', '.mov', '.avi')

    @property
    def is_audio(self):
        """Return True if media_url points to an audio file (by MIME type or extension)."""
        if self.media_type.startswith('audio/'):
            return True
        url = self.media_url.lower()
        return any(url.endswith(ext) for ext in self._AUDIO_EXTS)

    @property
    def is_video(self):
        """Return True if media_url points to a video file (by MIME type or extension)."""
        if self.media_type.startswith('video/'):
            return True
        url = self.media_url.lower()
        return any(url.endswith(ext) for ext in self._VIDEO_EXTS)

    @property
    def short_summary(self):
        """Return summary truncated to ~220 chars at a word boundary."""
        if len(self.summary) > 220:
            return self.summary[:220].rsplit(' ', 1)[0] + '…'
        return self.summary
