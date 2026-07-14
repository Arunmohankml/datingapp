import os
import cloudinary
import cloudinary.uploader
from django.conf import settings
from PIL import Image
import io

# Configure Cloudinary
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
    secure = True
)

def _convert_to_webp(file_obj, quality=85):
    try:
        img = Image.open(file_obj)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        output = io.BytesIO()
        img.save(output, format='WEBP', quality=quality, optimize=True)
        output.seek(0)
        return output
    except Exception as e:
        print(f"WebP conversion failed: {e}")
        file_obj.seek(0)
        return file_obj

def upload_to_cloudinary(file_obj, folder="srm_match/misc", public_id=None, optimize=True):
    try:
        upload_data = _convert_to_webp(file_obj) if optimize else file_obj
        params = {
            "folder": folder,
            "resource_type": "image",
        }
        if public_id:
            params["public_id"] = public_id
            params["overwrite"] = True

        upload_result = cloudinary.uploader.upload(upload_data, **params)
        return upload_result.get('secure_url')
    except Exception as e:
        print(f"Cloudinary Upload Error: {e}")
        return None

def upload_base64_to_cloudinary(base64_str, folder="srm_match/verification"):
    try:
        if not base64_str.startswith('data:'):
            base64_str = f"data:image/jpeg;base64,{base64_str}"
        upload_result = cloudinary.uploader.upload(base64_str, folder=folder)
        return upload_result.get('secure_url')
    except Exception as e:
        print(f"Cloudinary Base64 Upload Error: {e}")
        return None
