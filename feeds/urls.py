from django.urls import path
from . import views

urlpatterns = [
    path('', views.ArticleListView.as_view(), name='article_list'),
    path('c/<slug:category_slug>/', views.ArticleListView.as_view(), name='article_list_category'),
    path('m/<slug:medio_slug>/', views.ArticleListView.as_view(), name='article_list_medio'),
    path('a/<int:pk>/', views.ArticleDetailView.as_view(), name='article_detail'),
    path('refresh/', views.PublicFetchView.as_view(), name='public_fetch'),
    path('opml/<uuid:pk>/', views.OPMLServeView.as_view(), name='opml_serve'),
    path('api/new-count/', views.NewArticlesCountView.as_view(), name='new_articles_count'),
]
