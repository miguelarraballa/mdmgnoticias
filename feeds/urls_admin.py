from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.AdminLoginView.as_view(), name='admin_login'),
    path('logout/', views.AdminLogoutView.as_view(), name='admin_logout'),
    path('', views.DashboardView.as_view(), name='admin_dashboard'),
    path('feeds/', views.FeedListView.as_view(), name='admin_feed_list'),
    path('feeds/add/', views.FeedCreateView.as_view(), name='admin_feed_add'),
    path('feeds/<int:pk>/edit/', views.FeedUpdateView.as_view(), name='admin_feed_edit'),
    path('feeds/<int:pk>/delete/', views.FeedDeleteView.as_view(), name='admin_feed_delete'),
    path('categories/', views.CategoryListView.as_view(), name='admin_category_list'),
    path('categories/add/', views.CategoryCreateView.as_view(), name='admin_category_add'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='admin_category_edit'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='admin_category_delete'),
    path('fetch/', views.FetchNowView.as_view(), name='admin_fetch_now'),
    path('fetch-batch/', views.FetchBatchAPIView.as_view(), name='admin_fetch_batch'),
    path('feeds/<int:pk>/test/', views.FeedTestView.as_view(), name='admin_feed_test'),
    path('feeds/<int:pk>/opml-import/', views.OPMLImportView.as_view(), name='admin_opml_import'),
    path('medios/', views.MedioListView.as_view(), name='admin_medio_list'),
    path('medios/add/', views.MedioCreateView.as_view(), name='admin_medio_add'),
    path('medios/<int:pk>/edit/', views.MedioUpdateView.as_view(), name='admin_medio_edit'),
    path('medios/<int:pk>/delete/', views.MedioDeleteView.as_view(), name='admin_medio_delete'),
    path('settings/', views.SettingsView.as_view(), name='admin_settings'),
    path('opml/', views.OPMLUploadListView.as_view(), name='admin_opml_list'),
    path('opml/<uuid:pk>/delete/', views.OPMLDeleteView.as_view(), name='admin_opml_delete'),
]
