import os
import sys
import traceback

# Ensure settings module is set
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')

try:
    from django.core.wsgi import get_wsgi_application
    app = get_wsgi_application()
    application = app
except Exception as e:
    print("!!! VERCEL STARTUP ERROR !!!")
    print(f"Error Type: {type(e).__name__}")
    print(f"Error Message: {str(e)}")
    traceback.print_exc()
    # Still raise it so Vercel knows it failed, but now we'll see the logs
    raise e
