import os
from django.conf import settings

# EXTREME LAZY LOADING: No top-level ImageKit imports to prevent Vercel startup crashes
def get_imagekit_instance():
    """
    Lazy initialization of ImageKit 5.x Client with internal imports.
    This ensures the app boots even if the library is missing.
    """
    try:
        from imagekitio import ImageKit
        
        private_key = os.environ.get("IMAGEKIT_PRIVATE_KEY") or getattr(settings, 'IMAGEKIT_PRIVATE_KEY', None)
        
        if not private_key:
            print("DEBUG: ImageKit Private Key missing. Initialization skipped.")
            return None
            
        return ImageKit(private_key=private_key)
    except ImportError:
        print("DEBUG: imagekitio library not found in environment.")
        return None
    except Exception as e:
        print(f"DEBUG: Failed to initialize ImageKit 5.x: {e}")
        return None

def upload_to_imagekit(file_obj, folder="/user_uploads"):
    """
    Uploads a file object to ImageKit using v5.x SDK with extreme lazy loading.
    Returns the file URL if successful, else None.
    """
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
        
        # In 5.x, the response might be a pydantic model or dict
        if upload_response:
            if hasattr(upload_response, 'url'):
                print(f"DEBUG: ImageKit 5.x upload success (attr): {upload_response.url}")
                return upload_response.url
            if isinstance(upload_response, dict) and 'url' in upload_response:
                print(f"DEBUG: ImageKit 5.x upload success (dict): {upload_response['url']}")
                return upload_response['url']
        
        print(f"DEBUG: ImageKit 5.x upload failed - no URL in response: {upload_response}")
        return None
        
    except Exception as e:
        print(f"DEBUG: ImageKit 5.x Upload Exception: {str(e)}")
        return None
