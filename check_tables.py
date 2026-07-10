import os
from dotenv import load_dotenv
load_dotenv()
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
DATABASE_URL = os.environ.get('DATABASE_URL')
print(f"Supabase URL: {'set' if SUPABASE_URL else 'NOT set'}")
print(f"Supabase Key: {'set' if SUPABASE_KEY else 'NOT set'}")
print(f"Database URL: {'set' if DATABASE_URL else 'NOT set'}")
