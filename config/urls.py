from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('panel/', include('feeds.urls_admin')),
    path('', include('feeds.urls')),
]
