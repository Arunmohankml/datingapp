import os
from django.core.wsgi import get_wsgi_application

# Ensure settings module is set
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')

# Absolute minimum assignment for Vercel scanner
app = get_wsgi_application()
application = app
