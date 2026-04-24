import traceback
import sys

class ExceptionLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            # Full traceback to console (which Vercel captures)
            print("--- EXCEPTION LOG START ---")
            print(f"Path: {request.path}")
            print(f"Error: {str(e)}")
            traceback.print_exc()
            print("--- EXCEPTION LOG END ---")
            raise e
