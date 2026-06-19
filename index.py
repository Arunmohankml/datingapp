import os
from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise

# Ensure settings module is set
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')

# Wrap with WhiteNoise for static file serving at WSGI level
application = WhiteNoise(get_wsgi_application())
app = application
