import django, os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')
django.setup()
from django.db import connection
with connection.cursor() as c:
    c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='home_event' AND column_name='slug'")
    r = c.fetchone()
    print('slug column exists:', r is not None)
