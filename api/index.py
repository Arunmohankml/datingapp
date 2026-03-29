import os
import sys
from pathlib import Path

# Fix the Python Path for Vercel’s serverless environment
BASE_DIR = Path(__file__).resolve().parent.parent
# Look for modules in the root and in the nested project folder
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "datingapp"))

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')

# Import the WSGI application from the inner datingapp folder
from datingapp.wsgi import application

# Alias for Vercel's entry point
app = application
