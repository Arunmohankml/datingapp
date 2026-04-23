import os
import django
import sys

# Add current directory to path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')
django.setup()

from home.models import Profile

# Get the latest updated profile
p = Profile.objects.order_by('-updated_at').first()
if p:
    print(f"Profile: {p.name}")
    print(f"Campus: {p.campus}")
    print(f"Course: {p.course}")
    print(f"Branch: {p.branch}")
    print(f"Year: {p.clg_year}")
    print(f"Languages: {p.languages}")
    print(f"Interests: {p.interest_tags}")
else:
    print("No profiles found.")
