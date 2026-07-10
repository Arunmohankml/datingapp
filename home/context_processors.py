from django.conf import settings
from .models import Message, MatchRequest, SupportTicket
from .campus_config import get_campus_options, get_campus_short_options, get_all_campuses, get_org_groups

def unread_messages_count(request):
    base_ctx = {
        'PUSHER_KEY': getattr(settings, 'PUSHER_KEY', ''),
        'PUSHER_CLUSTER': getattr(settings, 'PUSHER_CLUSTER', 'ap2'),
        'admin_emails': getattr(settings, 'ADMIN_EMAILS', []),
    }
    if request.user.is_authenticated:
        try:
            unread_count = Message.objects.filter(receiver=request.user, is_read=False).count()
            pending_count = MatchRequest.objects.filter(receiver=request.user, status='pending').count()
            fb_unread = SupportTicket.objects.filter(user=request.user, unread__gt=0).count()
        except Exception as exc:
            print(f"unread_messages_count context failed: {exc}")
            unread_count = 0
            pending_count = 0
            fb_unread = 0
        return {
            **base_ctx,
            'global_unread_count': unread_count,
            'pending_connections_count': pending_count,
            'feedback_unread_count': fb_unread,
        }
    return {
        **base_ctx,
        'global_unread_count': 0,
        'pending_connections_count': 0,
        'feedback_unread_count': 0,
    }

def campus_options(request):
    return {
        'campus_options': get_campus_options(),
        'campus_short_options': get_campus_short_options(),
        'all_campuses': get_all_campuses(),
        'campus_org_groups': get_org_groups(),
    }
