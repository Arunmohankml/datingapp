import os
import sys
import traceback

# Ensure settings module is set
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')

print("--- STARTING IMPORT TEST ---")
try:
    import home.views
    print("--- home.views IMPORT SUCCESS ---")
except Exception as e:
    print("!!! home.views IMPORT ERROR !!!")
    print(f"Error: {type(e).__name__}: {str(e)}")
    traceback.print_exc()

from django.core.wsgi import get_wsgi_application
app = get_wsgi_application()
application = app
