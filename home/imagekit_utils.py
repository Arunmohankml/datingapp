import os
import base64
from imagekitio import ImageKit
from django.conf import settings

# Configuration from Environment Variables (set in Vercel)
IK_PRIVATE_KEY = os.environ.get("IMAGEKIT_PRIVATE_KEY", "private_qXEUvhHsNdmxrM8AqiEZzlfUg3s=")

# Initialize ImageKit 5.x Client
# In v5.x, the constructor only takes private_key. 
# It handles public_key/url_endpoint differently or implicitly via API calls.
def get_imagekit_instance():
    try:
        return ImageKit(
            private_key=IK_PRIVATE_KEY
        )
    except Exception as e:
        print(f"DEBUG: Failed to initialize ImageKit 5.x: {e}")
        return None

imagekit = get_imagekit_instance()

def upload_to_imagekit(file_obj, folder="/user_uploads"):
    """
    Uploads a file object to ImageKit using v5.x SDK.
    Returns the file URL if successful, else None.
    """
    if not imagekit:
        print("DEBUG: ImageKit instance is not available.")
        return None
        
    try:
        # Read file content
        file_obj.seek(0)
        file_content = file_obj.read()
        
        print(f"DEBUG: Starting ImageKit 5.x upload for {file_obj.name} to {folder}...")
        
        # ImageKit 5.x uses ik.files.upload()
        upload_response = imagekit.files.upload(
            file=file_content,
            file_name=file_obj.name,
            folder=folder,
            use_unique_file_name=True
        )
        
        if upload_response and hasattr(upload_response, 'url'):
            print(f"DEBUG: ImageKit 5.x upload success: {upload_response.url}")
            return upload_response.url
        
        print(f"DEBUG: ImageKit 5.x upload failed - no URL in response: {upload_response}")
        return None
        
    except Exception as e:
        print(f"DEBUG: ImageKit 5.x Upload Exception: {str(e)}")
        return None
