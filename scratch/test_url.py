import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Missing Supabase credentials")
    exit()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
url = supabase.storage.from_('images').get_public_url('test.jpg')
print(f"URL Type: {type(url)}")
print(f"URL Value: {url}")
