import os
from django.core.wsgi import get_wsgi_application

# Ensure settings module is set
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')

# Standard Vercel entry point
# Vercel's build-time scanner requires this to be a top-level assignment
app = get_wsgi_application()
application = app
