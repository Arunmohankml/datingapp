import os
import sys
import django
from io import BytesIO

# Setup Django environment
sys.path.append('c:\\Users\\USER\\Desktop\\Projects\\DATING APP')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datingapp.settings')
django.setup()

from home.supabase_utils import upload_to_supabase, upload_base64_to_supabase
import base64

def test_supabase():
    print("Testing Base64 Upload...")
    # Create a tiny 1x1 black image in base64
    tiny_image_b64 = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
    
    url = upload_base64_to_supabase(tiny_image_b64, bucket="images", path="test")
    if url:
        print(f"SUCCESS! URL: {url}")
    else:
        print("FAILED base64 upload.")
        
    print("\nTesting File Upload...")
    class MockFile:
        def __init__(self, data, name):
            self.data = data
            self.name = name
        def read(self):
            return self.data
        def seek(self, pos):
            pass

    raw_data = base64.b64decode(tiny_image_b64.split(',')[1])
    mock_file = MockFile(raw_data, "test.jpg")
    url2 = upload_to_supabase(mock_file, bucket="images", path="test")
    
    if url2:
        print(f"SUCCESS! URL: {url2}")
    else:
        print("FAILED file upload.")

if __name__ == "__main__":
    test_supabase()
