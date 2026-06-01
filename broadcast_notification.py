import os
import json
import django
import firebase_admin
from firebase_admin import credentials, messaging
import re

# 1. Setup Django environment to access models and settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')
django.setup()

from home.models import FCMToken
from django.conf import settings

def get_firebase_app():
    """Initializes Firebase using the same logic as the web app."""
    if not firebase_admin._apps:
        try:
            cert_path = os.path.join(settings.BASE_DIR, 'serviceAccountKey.json')
            if os.path.exists(cert_path):
                cred = credentials.Certificate(cert_path)
                firebase_admin.initialize_app(cred)
            else:
                config_str = os.environ.get('FIREBASE_SERVICE_ACCOUNT', '').strip()
                if not config_str:
                    print("Error: FIREBASE_SERVICE_ACCOUNT environment variable is missing.")
                    return None
                
                # Handle potential wrapping quotes from env loaders
                if (config_str.startswith('"') and config_str.endswith('"')) or \
                   (config_str.startswith("'") and config_str.endswith("'")):
                    config_str = config_str[1:-1]
                
                # Parse JSON with robust newline handling for private keys
                try:
                    cred_dict = json.loads(config_str.replace('\\n', '\n'), strict=False)
                except:
                    cred_dict = json.loads(config_str, strict=False)
                
                if cred_dict and 'private_key' in cred_dict:
                    pk = cred_dict['private_key']
                    cred_dict['private_key'] = re.sub(r'\\+n', '\n', pk).replace('\r', '')
                
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
            print("Firebase initialized successfully.")
        except Exception as e:
            print(f"Firebase Init Error: {e}")
            return None
    return firebase_admin.get_app()

def run_broadcast():
    # Ensure Firebase is ready
    app = get_firebase_app()
    if not app:
        return

    # Get user input for the notification
    print("\n--- SRM Sparks Broadcast System ---")
    title = input("Enter Notification Title: ").strip()
    body = input("Enter Notification Body: ").strip()
    url = input("Enter Target URL Path (default: /): ").strip() or "/"

    if not title or not body:
        print("Error: Title and Body cannot be empty.")
        return

    # Fetch all unique tokens
    tokens = list(FCMToken.objects.values_list('token', flat=True).distinct())
    
    if not tokens:
        print("No active FCM tokens found in the database.")
        return

    print(f"Found {len(tokens)} unique tokens. Preparing broadcast...")

    # Build the absolute URL for the notification link
    domain = os.environ.get('VERCEL_URL', 'srm-match.vercel.app')
    if not domain.startswith('http'):
        domain = f"https://{domain}"
    absolute_url = f"{domain.rstrip('/')}/{url.lstrip('/')}"

    # Firebase limits multicast messages to 500 tokens per call
    batch_size = 500
    for i in range(0, len(tokens), batch_size):
        token_batch = tokens[i : i + batch_size]
        
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data={'url': url, 'title': title, 'body': body},
            tokens=token_batch,
            webpush=messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    icon='/icon-192x192.png',
                    badge='/icon-192x192.png',
                ),
                fcm_options=messaging.WebpushFCMOptions(link=absolute_url)
            )
        )

        response = messaging.send_each_for_multicast(message)
        print(f"Batch {i//batch_size + 1}: Success: {response.success_count}, Failure: {response.failure_count}")

if __name__ == "__main__":
    run_broadcast()