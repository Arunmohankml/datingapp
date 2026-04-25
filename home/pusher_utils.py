import pusher
from django.conf import settings

def get_pusher_client():
    if not all([settings.PUSHER_APP_ID, settings.PUSHER_KEY, settings.PUSHER_SECRET]):
        return None
        
    return pusher.Pusher(
        app_id=settings.PUSHER_APP_ID,
        key=settings.PUSHER_KEY,
        secret=settings.PUSHER_SECRET,
        cluster=settings.PUSHER_CLUSTER,
        ssl=True
    )

def broadcast_event(channel, event, data):
    pusher_client = get_pusher_client()
    if pusher_client:
        try:
            pusher_client.trigger(channel, event, data)
            return True
        except Exception as e:
            print(f"Pusher Error: {e}")
            return False
    return False
