import os
from django.core.wsgi import get_wsgi_application

# Ensure settings module is set
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')

# Standard Vercel entry point
app = get_wsgi_application()
application = app
