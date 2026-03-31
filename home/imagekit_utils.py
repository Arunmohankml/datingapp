import os
import base64
from imagekitio import ImageKit
from django.conf import settings

# Configuration with careful fallbacks
def get_imagekit_instance():
    """
    Lazy initialization of ImageKit 5.x Client.
    Returns None if missing credentials instead of crashing.
    """
    private_key = os.environ.get("IMAGEKIT_PRIVATE_KEY") or getattr(settings, 'IMAGEKIT_PRIVATE_KEY', None)
    
    if not private_key:
        print("DEBUG: ImageKit Private Key missing. Initialization skipped.")
        return None
        
    try:
        # In v5.x, the constructor only takes private_key. 
        return ImageKit(private_key=private_key)
    except Exception as e:
        print(f"DEBUG: Failed to initialize ImageKit 5.x: {e}")
        return None

def upload_to_imagekit(file_obj, folder="/user_uploads"):
    """
    Uploads a file object to ImageKit using v5.x SDK with lazy client creation.
    Returns the file URL if successful, else None.
    """
    # Lazy Init: Prevents startup crashes if library has issues
    ik = get_imagekit_instance()
    
    if not ik:
        print("DEBUG: ImageKit client not available for upload.")
        return None
        
    try:
        # Read file content
        file_obj.seek(0)
        file_content = file_obj.read()
        
        print(f"DEBUG: Starting ImageKit 5.x upload for {file_obj.name} to {folder}...")
        
        # ImageKit 5.x uses ik.files.upload()
        upload_response = ik.files.upload(
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
