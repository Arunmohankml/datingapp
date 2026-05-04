import os
from django.core.wsgi import get_wsgi_application

# Ensure settings module is set
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')

# Vercel's build-time scanner requires this to be a top-level assignment
# to a variable named 'app' or 'application'.
try:
    application = get_wsgi_application()
    app = application
except Exception as e:
    import traceback
    print("!!! VERCEL STARTUP ERROR !!!")
    traceback.print_exc()
    raise e
