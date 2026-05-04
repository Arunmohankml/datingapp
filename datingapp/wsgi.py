import os
import sys
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')

try:
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
except Exception as e:
    print("!!! WSGI STARTUP ERROR !!!")
    traceback.print_exc()
    raise e

app = application
