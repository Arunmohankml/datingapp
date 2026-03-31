import os
from imagekitio import ImageKit
from django.conf import settings

# Configuration from Environment Variables (set in Vercel)
# with hardcoded fallbacks for local development
IK_PUBLIC_KEY = os.environ.get("IMAGEKIT_PUBLIC_KEY", "public_t9vvNeEKiVs9c7CpHjKHek0V+Aw=")
IK_PRIVATE_KEY = os.environ.get("IMAGEKIT_PRIVATE_KEY", "private_qXEUvhHsNdmxrM8AqiEZzlfUg3s=")
IK_URL_ENDPOINT = os.environ.get("IMAGEKIT_URL_ENDPOINT", "https://ik.imagekit.io/anlsbeoqrq")

# Initialize ImageKit lazily or defensively
def get_imagekit_instance():
    try:
        return ImageKit(
            public_key=IK_PUBLIC_KEY,
            private_key=IK_PRIVATE_KEY,
            url_endpoint=IK_URL_ENDPOINT
        )
    except Exception as e:
        print(f"DEBUG: Failed to initialize ImageKit: {e}")
        return None

imagekit = get_imagekit_instance()

def upload_to_imagekit(file_obj, folder="/user_uploads"):
    """
    Uploads a file object to ImageKit.
    Returns the file URL if successful, else None.
    """
    if not imagekit:
        print("DEBUG: ImageKit instance is not available.")
        return None
        
    try:
        # Read file content
        file_obj.seek(0)
        file_content = file_obj.read()
        
        print(f"DEBUG: Starting ImageKit upload for {file_obj.name} to {folder}...")
        
        # ImageKit Python SDK can handle files/base64
        # We'll use the file content directly
        upload_response = imagekit.upload_file(
            file=file_content,
            file_name=file_obj.name,
            options={
                "folder": folder,
                "use_unique_file_name": True,
            }
        )
        
        if upload_response and hasattr(upload_response, 'url'):
            print(f"DEBUG: ImageKit upload success: {upload_response.url}")
            return upload_response.url
        
        print(f"DEBUG: ImageKit upload failed - no URL in response: {upload_response}")
        return None
        
    except Exception as e:
        print(f"DEBUG: ImageKit Upload Exception: {str(e)}")
        return None
