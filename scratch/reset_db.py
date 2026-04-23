import os
import sys
import django

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')
django.setup()

from django.contrib.auth.models import User
from home.models import Profile, ProfileImage, Message, MatchRequest, Question, UserAnswer, Confession

def reset_database():
    print("Starting full database reset...")
    
    # 1. Delete all Users (Cascades to Profiles, Messages, MatchRequests, etc.)
    user_count = User.objects.all().count()
    User.objects.all().delete()
    print(f"Deleted {user_count} users and all associated data.")

    # 2. Delete any orphaned data (if any)
    ProfileImage.objects.all().delete()
    UserAnswer.objects.all().delete()
    Confession.objects.all().delete()
    
    # Note: We keep Questions and Options as they are the "engine" of the app.
    
    print("Database is now clean and fresh!")

if __name__ == "__main__":
    reset_database()
