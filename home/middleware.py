import traceback
import sys
import re
from django.http import HttpResponseForbidden
from django.utils.html import format_html

# Paths that are always allowed (login, static assets, admin)
EXEMPT_PATHS = re.compile(
    r'^/(login|logout|static|admin|favicon|api/verify-token|api/save-fcm-token)/'
)

_BAN_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Access Denied — SRM Sparks</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #f1f5f9;
            display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
    .card {{ text-align: center; padding: 40px 30px; max-width: 420px; }}
    .icon {{ font-size: 64px; margin-bottom: 16px; }}
    h1 {{ font-size: 22px; font-weight: 800; margin-bottom: 10px; color: #ef4444; }}
    p {{ font-size: 14px; color: #94a3b8; line-height: 1.6; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">🚫</div>
    <h1>You have been banned</h1>
    <p>Your access to SRM Sparks has been suspended due to a violation of our community rules.<br><br>
       If you believe this is a mistake, please contact the admin team.</p>
  </div>
</body>
</html>
"""


class ExceptionLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            print("--- EXCEPTION LOG START ---")
            print(f"Path: {request.path}")
            print(f"Error: {str(e)}")
            traceback.print_exc()
            print("--- EXCEPTION LOG END ---")
            raise e


class BanMiddleware:
    """
    Site-wide ban enforcement.
    Checks:
      1. Logged-in user's profile.is_banned → hard block
      2. Fingerprint from cookie 'fp' or header 'X-Fingerprint' in BannedIdentifier (non-shadow)
      3. Client IP in BannedIdentifier (non-shadow)

    Exempt: login/logout/static/admin paths so the banned page is reachable.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip exempt paths
        if EXEMPT_PATHS.match(request.path):
            return self.get_response(request)

        try:
            from .models import BannedIdentifier

            # ── 1. Logged-in user ban ──
            if request.user.is_authenticated:
                profile = getattr(request.user, 'profile', None)
                if profile and profile.is_banned:
                    return HttpResponseForbidden(_BAN_HTML, content_type='text/html')

            # ── 2. Fingerprint ban (hard only — shadow ban is invisible) ──
            fingerprint = (
                request.COOKIES.get('fp') or
                request.headers.get('X-Fingerprint', '') or
                request.POST.get('fingerprint', '') or
                request.GET.get('fingerprint', '')
            )
            if fingerprint:
                if BannedIdentifier.objects.filter(
                    fingerprint=fingerprint, is_shadow_ban=False
                ).exists():
                    return HttpResponseForbidden(_BAN_HTML, content_type='text/html')

            # ── 3. IP ban ──
            ip = self._get_ip(request)
            if ip:
                if BannedIdentifier.objects.filter(
                    fingerprint=ip, is_shadow_ban=False
                ).exists():
                    return HttpResponseForbidden(_BAN_HTML, content_type='text/html')

        except Exception:
            # Never crash the site over ban check failures
            pass

        return self.get_response(request)

    @staticmethod
    def _get_ip(request):
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
