import os
import sys
import traceback

try:
    from django.core.wsgi import get_wsgi_application
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')
    application = get_wsgi_application()
    app = application
except Exception as e:
    print("CRITICAL STARTUP ERROR:")
    traceback.print_exc()
    # In case of crash, define a dummy app that returns the error
    def app(environ, start_response):
        status = '500 Internal Server Error'
        headers = [('Content-type', 'text/plain')]
        start_response(status, headers)
        return [f"Startup Error: {str(e)}\n\n{traceback.format_exc()}".encode('utf-8')]
