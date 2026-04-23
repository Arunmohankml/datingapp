import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Try to upload to profile_pics
data = b"test data"
try:
    print("Attempting upload to images/profile_pics/test.txt...")
    res = supabase.storage.from_('images').upload(
        path="profile_pics/test.txt",
        file=data,
        file_options={"content-type": "text/plain", "x-upsert": "true"}
    )
    print(f"Upload Result: {res}")
except Exception as e:
    print(f"Upload Error: {e}")
