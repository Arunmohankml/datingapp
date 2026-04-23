from .models import Message, MatchRequest

def unread_messages_count(request):
    if request.user.is_authenticated:
        unread_count = Message.objects.filter(receiver=request.user, is_read=False).count()
        pending_count = MatchRequest.objects.filter(receiver=request.user, status='pending').count()
        return {
            'global_unread_count': unread_count,
            'pending_connections_count': pending_count
        }
    return {
        'global_unread_count': 0,
        'pending_connections_count': 0
    }
