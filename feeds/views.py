import json
import time

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from .utils import fetch_raw, find_favicon, is_opml, parse_feed, parse_opml
from feeds.management.commands.fetch_feeds import fetch_feed_batch
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.management import call_command
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import DetailView

from .forms import CategoryForm, FeedForm, MedioForm, SiteConfigForm
from .models import Article, Category, Feed, Medio, SiteConfig, UploadedOPML


def _public_context():
    return {
        'categories': Category.objects.all(),
        'medios': Medio.objects.all(),
    }


# ---------------------------------------------------------------------------
# Public views
# ---------------------------------------------------------------------------

class ArticleListView(View):
    def get(self, request, category_slug=None, medio_slug=None):
        articles = Article.objects.select_related('feed', 'feed__category', 'feed__medio')
        active_category = None
        active_medio = None

        if category_slug:
            active_category = get_object_or_404(Category, slug=category_slug)
            articles = articles.filter(feed__category=active_category)

        if medio_slug:
            active_medio = get_object_or_404(Medio, slug=medio_slug)
            articles = articles.filter(feed__medio=active_medio)

        sort = request.GET.get('sort', 'id')
        if sort == 'date':
            articles = articles.order_by('-published_at')
        else:
            sort = 'id'
            articles = articles.order_by('-id')

        paginator = Paginator(articles, getattr(settings, 'ARTICLES_PER_PAGE', 20))
        page = paginator.get_page(request.GET.get('page'))

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render(request, 'feeds/article_cards.html', {'page_obj': page}).content.decode()
            return JsonResponse({'html': html, 'has_next': page.has_next(),
                                 'next_page': page.next_page_number() if page.has_next() else None})

        return render(request, 'feeds/article_list.html', {
            'page_obj': page,
            'active_category': active_category,
            'active_medio': active_medio,
            'sort': sort,
            **_public_context(),
        })


REFRESH_COOLDOWN = 300  # segundos entre refrescos por sesión
FETCH_BATCH_SIZE = 1  # 1 feed por petición para no superar el timeout de gunicorn (30s)


class PublicFetchView(View):
    def post(self, request):
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        try:
            body = json.loads(request.body) if is_ajax else {}
            offset = int(body.get('offset', 0))
            batch_size = int(body.get('batch_size', FETCH_BATCH_SIZE))
        except (ValueError, TypeError, json.JSONDecodeError):
            offset, batch_size = 0, FETCH_BATCH_SIZE

        if offset == 0:
            last = request.session.get('last_fetch', 0)
            now = time.time()
            if now - last < REFRESH_COOLDOWN:
                remaining = int(REFRESH_COOLDOWN - (now - last))
                if is_ajax:
                    return JsonResponse({'ok': False, 'cooldown': remaining,
                                         'message': f'Espera {remaining}s'})
                messages.warning(request, f'Espera {remaining}s antes de volver a refrescar.')
                return redirect(request.META.get('HTTP_REFERER', '/'))
            request.session['last_fetch'] = time.time()

        try:
            result = fetch_feed_batch(offset, batch_size)
            if is_ajax:
                return JsonResponse({'ok': True, **result})
            messages.success(request, 'Noticias actualizadas.')
        except Exception as e:
            if is_ajax:
                return JsonResponse({'ok': False, 'message': str(e)}, status=500)
            messages.error(request, f'Error al actualizar: {e}')

        return redirect(request.META.get('HTTP_REFERER', '/'))


class ArticleDetailView(DetailView):
    model = Article
    template_name = 'feeds/article_detail.html'
    context_object_name = 'article'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_public_context())
        return ctx


# ---------------------------------------------------------------------------
# Admin panel views (login required)
# ---------------------------------------------------------------------------

admin_required = login_required(login_url='/panel/login/')


class AdminLoginView(LoginView):
    template_name = 'admin_panel/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return '/panel/'


class AdminLogoutView(LogoutView):
    next_page = '/'


@method_decorator(admin_required, name='dispatch')
class DashboardView(View):
    def get(self, request):
        feeds = Feed.objects.select_related('category').order_by('name')
        return render(request, 'admin_panel/dashboard.html', {
            'feeds': feeds,
            'article_count': Article.objects.count(),
            'feed_count': Feed.objects.count(),
            'category_count': Category.objects.count(),
        })


@method_decorator(admin_required, name='dispatch')
class FeedListView(View):
    def get(self, request):
        feeds = Feed.objects.select_related('category').order_by('name')
        return render(request, 'admin_panel/feed_list.html', {'feeds': feeds})


@method_decorator(admin_required, name='dispatch')
class FeedCreateView(View):
    def get(self, request):
        return render(request, 'admin_panel/feed_form.html', {'form': FeedForm(), 'action': 'Añadir'})

    def post(self, request):
        form = FeedForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Feed añadido correctamente.')
            return redirect('admin_feed_list')
        return render(request, 'admin_panel/feed_form.html', {'form': form, 'action': 'Añadir'})


@method_decorator(admin_required, name='dispatch')
class FeedUpdateView(View):
    def get(self, request, pk):
        feed = get_object_or_404(Feed, pk=pk)
        return render(request, 'admin_panel/feed_form.html', {'form': FeedForm(instance=feed), 'action': 'Editar', 'feed': feed})

    def post(self, request, pk):
        feed = get_object_or_404(Feed, pk=pk)
        form = FeedForm(request.POST, instance=feed)
        if form.is_valid():
            form.save()
            messages.success(request, 'Feed actualizado.')
            return redirect('admin_feed_list')
        return render(request, 'admin_panel/feed_form.html', {'form': form, 'action': 'Editar', 'feed': feed})


@method_decorator(admin_required, name='dispatch')
class FeedDeleteView(View):
    def get(self, request, pk):
        feed = get_object_or_404(Feed, pk=pk)
        return render(request, 'admin_panel/feed_delete.html', {'feed': feed})

    def post(self, request, pk):
        feed = get_object_or_404(Feed, pk=pk)
        feed.delete()
        messages.success(request, 'Feed eliminado.')
        return redirect('admin_feed_list')


@method_decorator(admin_required, name='dispatch')
class CategoryListView(View):
    def get(self, request):
        categories = Category.objects.all()
        return render(request, 'admin_panel/category_list.html', {'categories': categories})


@method_decorator(admin_required, name='dispatch')
class CategoryCreateView(View):
    def get(self, request):
        return render(request, 'admin_panel/category_form.html', {'form': CategoryForm(), 'action': 'Añadir'})

    def post(self, request):
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría añadida.')
            return redirect('admin_category_list')
        return render(request, 'admin_panel/category_form.html', {'form': form, 'action': 'Añadir'})


@method_decorator(admin_required, name='dispatch')
class CategoryUpdateView(View):
    def get(self, request, pk):
        cat = get_object_or_404(Category, pk=pk)
        return render(request, 'admin_panel/category_form.html', {'form': CategoryForm(instance=cat), 'action': 'Editar', 'category': cat})

    def post(self, request, pk):
        cat = get_object_or_404(Category, pk=pk)
        form = CategoryForm(request.POST, instance=cat)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría actualizada.')
            return redirect('admin_category_list')
        return render(request, 'admin_panel/category_form.html', {'form': form, 'action': 'Editar', 'category': cat})


@method_decorator(admin_required, name='dispatch')
class CategoryDeleteView(View):
    def get(self, request, pk):
        cat = get_object_or_404(Category, pk=pk)
        return render(request, 'admin_panel/category_delete.html', {'category': cat})

    def post(self, request, pk):
        cat = get_object_or_404(Category, pk=pk)
        cat.delete()
        messages.success(request, 'Categoría eliminada.')
        return redirect('admin_category_list')


@method_decorator(admin_required, name='dispatch')
class FetchNowView(View):
    def post(self, request):
        # Legacy redirect-based endpoint (kept for non-JS fallback)
        try:
            call_command('fetch_feeds')
            messages.success(request, 'Feeds actualizados correctamente.')
        except Exception as e:
            messages.error(request, f'Error al actualizar feeds: {e}')
        return redirect('admin_dashboard')


@method_decorator(admin_required, name='dispatch')
class FetchBatchAPIView(View):
    def post(self, request):
        try:
            body = json.loads(request.body)
            offset = int(body.get('offset', 0))
            batch_size = int(body.get('batch_size', FETCH_BATCH_SIZE))
        except (ValueError, TypeError, json.JSONDecodeError):
            return JsonResponse({'ok': False, 'message': 'Parámetros inválidos'}, status=400)

        try:
            result = fetch_feed_batch(offset, batch_size)
            return JsonResponse({'ok': True, **result})
        except Exception as e:
            return JsonResponse({'ok': False, 'message': str(e)}, status=500)


@method_decorator(admin_required, name='dispatch')
class FeedTestView(View):
    def get(self, request, pk):
        feed = get_object_or_404(Feed, pk=pk)
        try:
            content, content_type = fetch_raw(feed.url)
        except Exception as e:
            return JsonResponse({'ok': False, 'message': str(e)})

        # ── OPML: return feed list for manual selection, don't auto-import ──
        if is_opml(content, content_type, feed.url):
            outlines = parse_opml(content)
            if not outlines:
                return JsonResponse({'ok': False, 'message': 'OPML sin feeds encontrados'})
            existing_urls = set(
                Feed.objects.filter(
                    url__in=[o['url'] for o in outlines]
                ).values_list('url', flat=True)
            )
            feeds_data = [
                {'name': o['name'], 'url': o['url'], 'existing': o['url'] in existing_urls}
                for o in outlines
            ]
            new_count = sum(1 for f in feeds_data if not f['existing'])
            return JsonResponse({
                'ok': True,
                'opml': True,
                'message': f'OPML · {len(outlines)} feeds encontrados · {new_count} nuevos',
                'feeds': feeds_data,
            })

        # ── RSS / Atom ─────────────────────────────────────────────────────
        parsed = parse_feed(content, feed.url)

        status = parsed.get('status', 0)
        bozo = parsed.get('bozo', False)
        entries = len(parsed.entries)
        title = parsed.feed.get('title', '') if hasattr(parsed, 'feed') else ''

        if status and status >= 400:
            return JsonResponse({'ok': False, 'message': f'HTTP {status}'})
        if entries == 0 and bozo:
            exc = str(parsed.get('bozo_exception', 'formato inválido'))
            return JsonResponse({'ok': False, 'message': f'Feed inválido: {exc}'})

        # Auto-detect favicon on the medio if not set
        favicon_saved = ''
        if feed.medio and not feed.medio.favicon_url:
            favicon = find_favicon(parsed, feed.url)
            if favicon:
                feed.medio.favicon_url = favicon
                feed.medio.save(update_fields=['favicon_url'])
                favicon_saved = favicon

        favicon_url = feed.medio.favicon_url if feed.medio else ''
        return JsonResponse({
            'ok': True,
            'message': f'{entries} entradas · {title or feed.url}',
            'favicon': favicon_url,
            'favicon_saved': bool(favicon_saved),
        })


@method_decorator(admin_required, name='dispatch')
class OPMLImportView(View):
    def post(self, request, pk):
        feed = get_object_or_404(Feed, pk=pk)
        try:
            body = json.loads(request.body)
            selected = body.get('feeds', [])
        except (ValueError, KeyError):
            return JsonResponse({'ok': False, 'message': 'Datos inválidos'}, status=400)

        created = 0
        for item in selected:
            url = item.get('url', '').strip()
            name = item.get('name', '').strip() or url
            if not url:
                continue
            _, new = Feed.objects.get_or_create(
                url=url,
                defaults={
                    'name': name,
                    'medio': feed.medio,
                    'category': feed.category,
                    'is_active': True,
                },
            )
            if new:
                created += 1

        return JsonResponse({'ok': True, 'created': created})


# ---------------------------------------------------------------------------
# Medio CRUD
# ---------------------------------------------------------------------------

@method_decorator(admin_required, name='dispatch')
class MedioListView(View):
    def get(self, request):
        medios = Medio.objects.all()
        return render(request, 'admin_panel/medio_list.html', {'medios': medios})


@method_decorator(admin_required, name='dispatch')
class MedioCreateView(View):
    def get(self, request):
        return render(request, 'admin_panel/medio_form.html', {'form': MedioForm(), 'action': 'Añadir'})

    def post(self, request):
        form = MedioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Medio añadido.')
            return redirect('admin_medio_list')
        return render(request, 'admin_panel/medio_form.html', {'form': form, 'action': 'Añadir'})


@method_decorator(admin_required, name='dispatch')
class MedioUpdateView(View):
    def get(self, request, pk):
        medio = get_object_or_404(Medio, pk=pk)
        return render(request, 'admin_panel/medio_form.html', {'form': MedioForm(instance=medio), 'action': 'Editar', 'medio': medio})

    def post(self, request, pk):
        medio = get_object_or_404(Medio, pk=pk)
        form = MedioForm(request.POST, instance=medio)
        if form.is_valid():
            form.save()
            messages.success(request, 'Medio actualizado.')
            return redirect('admin_medio_list')
        return render(request, 'admin_panel/medio_form.html', {'form': form, 'action': 'Editar', 'medio': medio})


@method_decorator(admin_required, name='dispatch')
class MedioDeleteView(View):
    def get(self, request, pk):
        medio = get_object_or_404(Medio, pk=pk)
        return render(request, 'admin_panel/medio_delete.html', {'medio': medio})

    def post(self, request, pk):
        medio = get_object_or_404(Medio, pk=pk)
        medio.delete()
        messages.success(request, 'Medio eliminado.')
        return redirect('admin_medio_list')


# ---------------------------------------------------------------------------
# OPML upload (admin) + serve (public)
# ---------------------------------------------------------------------------

@method_decorator(admin_required, name='dispatch')
class OPMLUploadListView(View):
    def get(self, request):
        uploads = UploadedOPML.objects.all()
        return render(request, 'admin_panel/opml_upload.html', {'uploads': uploads})

    def post(self, request):
        f = request.FILES.get('opml_file')
        if not f:
            return JsonResponse({'ok': False, 'message': 'No se ha seleccionado archivo'})
        try:
            raw = f.read()
            if not is_opml(raw, f.content_type or '', f.name):
                return JsonResponse({'ok': False, 'message': 'El archivo no parece ser un OPML válido'})
            try:
                text = raw.decode('utf-8-sig')  # strips BOM if present
            except UnicodeDecodeError:
                text = raw.decode('latin-1')
            obj = UploadedOPML.objects.create(filename=f.name, content=text)
            url = request.build_absolute_uri(reverse('opml_serve', args=[obj.pk]))
            return JsonResponse({'ok': True, 'url': url, 'filename': f.name, 'id': str(obj.pk)})
        except Exception as e:
            return JsonResponse({'ok': False, 'message': str(e)})


@method_decorator(admin_required, name='dispatch')
class OPMLDeleteView(View):
    def post(self, request, pk):
        obj = get_object_or_404(UploadedOPML, pk=pk)
        obj.delete()
        return JsonResponse({'ok': True})


class NewArticlesCountView(View):
    def get(self, request):
        try:
            after_id = int(request.GET.get('after', 0))
        except ValueError:
            after_id = 0
        category_slug = request.GET.get('category', '')
        medio_slug = request.GET.get('medio', '')

        articles = Article.objects.filter(pk__gt=after_id)
        if category_slug:
            articles = articles.filter(feed__category__slug=category_slug)
        if medio_slug:
            articles = articles.filter(feed__medio__slug=medio_slug)

        return JsonResponse({'count': articles.count()})


class OPMLServeView(View):
    def get(self, request, pk):
        obj = get_object_or_404(UploadedOPML, pk=pk)
        return HttpResponse(obj.content.encode('utf-8'), content_type='text/xml; charset=utf-8')


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@method_decorator(admin_required, name='dispatch')
class SettingsView(View):
    def get(self, request):
        form = SiteConfigForm(instance=SiteConfig.get())
        return render(request, 'admin_panel/settings.html', {'form': form})

    def post(self, request):
        form = SiteConfigForm(request.POST, instance=SiteConfig.get())
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuración guardada.')
            return redirect('admin_settings')
        return render(request, 'admin_panel/settings.html', {'form': form})
