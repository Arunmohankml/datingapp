import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')

# Boot the application safely. 
# Do NOT run long operations (like migrations) here, as Vercel will kill the function.
application = get_wsgi_application()

app = application
