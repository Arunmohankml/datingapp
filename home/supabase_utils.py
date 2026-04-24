import os
from supabase import create_client, Client
from django.conf import settings
from PIL import Image
import io
import uuid

# Initialize Supabase Client
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').strip()
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '').strip()

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("DEBUG: Supabase Client Initialized.")
    except Exception as e:
        print(f"CRITICAL ERROR: Supabase Initialization Failed: {e}")
else:
    print("WARNING: Supabase URL or Key missing in environment.")

def compress_image(file_obj, max_width=1000, quality=70):
    """
    Compresses image, resizes if needed, and converts to WebP.
    Returns BytesIO object of the compressed image.
    """
    try:
        img = Image.open(file_obj)
        
        # Convert to RGB if necessary (remove Alpha for JPEG/WebP compatibility if needed, 
        # but WebP supports Alpha. However, we stick to RGB for consistency unless requested otherwise)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        # Resize if width > max_width
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int(float(img.height) * float(ratio))
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        # Save to BytesIO as WebP
        output = io.BytesIO()
        img.save(output, format='WEBP', quality=quality, optimize=True)
        output.seek(0)
        return output
    except Exception as e:
        print(f"DEBUG: Compression failed: {e}")
        file_obj.seek(0)
        return file_obj

def upload_to_supabase(file_obj, bucket="images", path="dating_app/"):
    """
    Uploads a file to Supabase Storage and returns the public URL.
    Returns the file URL if successful, else None.
    """
    if not supabase:
        print("DEBUG: Supabase client not initialized. Check SUPABASE_URL and SUPABASE_KEY.")
        return None

    try:
        import time
        filename = getattr(file_obj, 'name', 'upload.jpg')
        # Add timestamp to avoid caching/conflict
        timestamp = int(time.time())
        filename = f"{timestamp}_{filename}"
        full_path = f"{path.strip('/')}/{filename}"
        
        print(f"DEBUG: Attempting upload to bucket '{bucket}' at path '{full_path}'")
        
        # Read file content
        file_obj.seek(0)
        
        # Reject very large files (e.g. > 10MB) before compression
        file_size = len(file_obj.read())
        if file_size > 10 * 1024 * 1024:
            print("DEBUG: File too large (>10MB). Rejecting.")
            return None
            
        file_obj.seek(0)
        
        # Backend Fallback Compression
        compressed_file = compress_image(file_obj)
        file_data = compressed_file.read()
        
        # Force filename extension to .webp for consistency
        name_parts = filename.split('.')
        name_base = ".".join(name_parts[:-1]) if len(name_parts) > 1 else filename
        full_path = f"{path.strip('/')}/{name_base}.webp"
        
        # Upload to Supabase Storage
        res = supabase.storage.from_(bucket).upload(
            path=full_path,
            file=file_data,
            file_options={"content-type": "image/webp", "x-upsert": "true"}
        )
        
        # Get Public URL
        public_url = supabase.storage.from_(bucket).get_public_url(full_path)
        print(f"DEBUG: Supabase upload success: {public_url}")
        return public_url
        
    except Exception as e:
        print(f"DEBUG: Supabase [UPLOAD ERROR]: {str(e)}")
        # Check if the error is just that the file already exists
        if "already exists" in str(e).lower():
            try:
                public_url = supabase.storage.from_(bucket).get_public_url(full_path)
                return public_url
            except:
                return None
        return None

def upload_base64_to_supabase(base64_str, bucket="images", path="verification"):
    """
    Decodes base64 string and uploads to Supabase Storage.
    """
    if not supabase: return None
    try:
        import base64
        import uuid
        if ',' in base64_str:
            base64_str = base64_str.split(',')[1]
        
        img_data = base64.b64decode(base64_str)
        filename = f"{uuid.uuid4()}.webp"
        full_path = f"{path.strip('/')}/{filename}"
        
        res = supabase.storage.from_(bucket).upload(
            path=full_path,
            file=img_data,
            file_options={"content-type": "image/webp", "x-upsert": "true"}
        )
        return supabase.storage.from_(bucket).get_public_url(full_path)
    except Exception as e:
        print(f"ERROR: Base64 upload failed: {e}")
        return None
