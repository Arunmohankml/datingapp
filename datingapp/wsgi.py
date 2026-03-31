import os
from django.core.wsgi import get_wsgi_application
from django.core.management import call_command

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')

application = get_wsgi_application()

# BRUTE FORCE: Auto-run migrations on Vercel startup
if os.environ.get('VERCEL'):
    try:
        print("Vercel starting up: Running migrations...")
        call_command('migrate', interactive=False)
    except Exception as e:
        print(f"Startup migration error: {str(e)}")

app = application
