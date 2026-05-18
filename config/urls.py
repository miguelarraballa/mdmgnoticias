from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('panel/', include('feeds.urls_admin')),
    path('', include('feeds.urls')),
]
