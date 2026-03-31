import cloudinary
import cloudinary.uploader
import os
from django.conf import settings

# Initialize Cloudinary Configuration
cloudinary.config(
    cloud_name = getattr(settings, 'CLOUDINARY_STORAGE', {}).get('CLOUD_NAME', ''),
    api_key = getattr(settings, 'CLOUDINARY_STORAGE', {}).get('API_KEY', ''),
    api_secret = getattr(settings, 'CLOUDINARY_STORAGE', {}).get('API_SECRET', ''),
    secure = True
)

def upload_to_cloudinary(file_obj, folder="dating_app"):
    """
    Uploads a file to Cloudinary and returns the secure URL.
    Returns the file URL if successful, else None.
    """
    print(f"DEBUG: upload_to_cloudinary entry point for file: {file_obj.name}")
    
    try:
        # Read file content (ensure pointer is at beginning)
        file_obj.seek(0)
        
        # Cloudinary SDK can handle file objects directly
        result = cloudinary.uploader.upload(
            file_obj,
            folder=folder,
            resource_type="auto"
        )
        
        print(f"DEBUG: Cloudinary raw response received: {result}")
        
        if 'secure_url' in result:
            print(f"DEBUG: Cloudinary upload success: {result['secure_url']}")
            return result['secure_url']
            
        print(f"DEBUG: Cloudinary upload failed - no secure_url in response: {result}")
        return None
        
    except Exception as e:
        print(f"DEBUG: Cloudinary [CRITICAL EXCEPTION] during upload: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
