import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("--- Files in 'images/gallery' ---")
res = supabase.storage.from_('images').list('gallery')
for f in res:
    print(f)

print("\n--- Files in 'images/profile_pics' ---")
res = supabase.storage.from_('images').list('profile_pics')
for f in res:
    print(f)
