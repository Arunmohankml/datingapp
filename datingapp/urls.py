"""
URL configuration for datingapp project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView, RedirectView
from django.http import FileResponse
import os
from home import views

def serve_template_file(request, filename, content_type):
    filepath = os.path.join(settings.BASE_DIR, 'template', filename)
    return FileResponse(open(filepath, 'rb'), content_type=content_type)

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include('home.urls')),
    path('privacy-policy/', views.privacy_policy_view, name='privacy_policy'),
    path('terms-and-conditions/', views.terms_and_conditions_view, name='terms_and_conditions'),
    path('community-guidelines/', views.community_guidelines_view, name='community_guidelines'),
    path('about/', views.about_view, name='about'),
    path('manifest.json', TemplateView.as_view(template_name='manifest.json', content_type='application/json')),
    path('sw.js', TemplateView.as_view(template_name='sw.js', content_type='application/javascript')),
    path('icon-192x192.png', lambda r: serve_template_file(r, 'icon-192x192.png', 'image/png')),
    path('icon-512x512.png', lambda r: serve_template_file(r, 'icon-512x512.png', 'image/png')),
    path('favicon.png', lambda r: serve_template_file(r, 'favicon.png', 'image/png')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
