import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')
django.setup()

from home.models import Profile

profile = Profile.objects.filter(name="baskaran nair").first()
if profile:
    print(f"Languages: {profile.languages} (Type: {type(profile.languages)})")
    print(f"Interests: {profile.interest_tags} (Type: {type(profile.interest_tags)})")
else:
    print("Profile not found")
