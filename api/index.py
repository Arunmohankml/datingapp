import os
import sys
from pathlib import Path

# Add the project directory to the path so Vercel can find everything
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(os.path.join(BASE_DIR, "datingapp"))

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')

# Import the WSGI application
from datingapp.wsgi import application # This is the datingapp folder inside datingapp/

# Export the application for Vercel
app = application
