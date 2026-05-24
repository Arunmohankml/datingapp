from django.conf import settings
from .models import Message, MatchRequest

def unread_messages_count(request):
    base_ctx = {
        'PUSHER_KEY': getattr(settings, 'PUSHER_KEY', ''),
        'PUSHER_CLUSTER': getattr(settings, 'PUSHER_CLUSTER', 'ap2'),
        'firebase_api_key': getattr(settings, 'FIREBASE_API_KEY', ''),
        'firebase_auth_domain': getattr(settings, 'FIREBASE_AUTH_DOMAIN', ''),
        'firebase_project_id': getattr(settings, 'FIREBASE_PROJECT_ID', ''),
        'firebase_storage_bucket': getattr(settings, 'FIREBASE_STORAGE_BUCKET', ''),
        'firebase_messaging_sender_id': getattr(settings, 'FIREBASE_MESSAGING_SENDER_ID', ''),
        'firebase_app_id': getattr(settings, 'FIREBASE_APP_ID', ''),
        'firebase_measurement_id': getattr(settings, 'FIREBASE_MEASUREMENT_ID', ''),
    }
    if request.user.is_authenticated:
        unread_count = Message.objects.filter(receiver=request.user, is_read=False).count()
        pending_count = MatchRequest.objects.filter(receiver=request.user, status='pending').count()
        return {
            **base_ctx,
            'global_unread_count': unread_count,
            'pending_connections_count': pending_count,
        }
    return {
        **base_ctx,
        'global_unread_count': 0,
        'pending_connections_count': 0,
    }
