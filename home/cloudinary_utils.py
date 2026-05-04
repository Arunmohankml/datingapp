import os
import cloudinary
import cloudinary.uploader
from django.conf import settings

# Configure Cloudinary
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
    secure = True
)

def upload_to_cloudinary(file_obj, folder="srm_match/misc", public_id=None):
    """
    Uploads a file object to Cloudinary and returns the secure URL.
    """
    try:
        # If it's a file path or file-like object
        params = {
            "folder": folder,
            "resource_type": "image",
        }
        if public_id:
            params["public_id"] = public_id
            params["overwrite"] = True

        upload_result = cloudinary.uploader.upload(file_obj, **params)
        return upload_result.get('secure_url')
    except Exception as e:
        print(f"Cloudinary Upload Error: {e}")
        return None

def upload_base64_to_cloudinary(base64_str, folder="srm_match/verification"):
    """
    Decodes base64 string and uploads to Cloudinary.
    """
    try:
        # Cloudinary uploader.upload supports data URIs directly
        # If the string doesn't have the prefix, add it if needed, 
        # but usually base64 strings from camera have 'data:image/jpeg;base64,...'
        if not base64_str.startswith('data:'):
            # Assume jpeg as fallback
            base64_str = f"data:image/jpeg;base64,{base64_str}"
            
        upload_result = cloudinary.uploader.upload(base64_str, folder=folder)
        return upload_result.get('secure_url')
    except Exception as e:
        print(f"Cloudinary Base64 Upload Error: {e}")
        return None
