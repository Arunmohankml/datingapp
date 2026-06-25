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
from home import views
from home import seo_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include('home.urls')),
    # SEO content hub
    path('campuses/', seo_views.seo_campuses_view, name='seo_campuses'),
    path('student-matching/', seo_views.seo_student_matching_view, name='seo_student_matching'),
    path('college-roommate-finder/', seo_views.seo_roommate_finder_view, name='seo_roommate_finder'),
    path('anonymous-campus-confessions/', seo_views.seo_confessions_view, name='seo_confessions'),
    path('campus-events/', seo_views.seo_campus_events_view, name='seo_campus_events'),
    path('campus/<slug:slug>/', seo_views.seo_campus_view, name='seo_campus'),
    path('founder/', seo_views.founder_view, name='founder'),
    path('privacy-policy/', views.privacy_policy_view, name='privacy_policy'),
    path('terms-and-conditions/', views.terms_and_conditions_view, name='terms_and_conditions'),
    path('community-guidelines/', views.community_guidelines_view, name='community_guidelines'),
    path('about/', views.about_view, name='about'),
    path('contact/', views.contact_view, name='contact'),
    path('manifest.json', TemplateView.as_view(template_name='manifest.json', content_type='application/json')),
    path('sw.js', TemplateView.as_view(template_name='sw.js', content_type='application/javascript')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
