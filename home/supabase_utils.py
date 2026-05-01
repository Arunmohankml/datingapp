import os
from supabase import create_client, Client
from django.conf import settings
from PIL import Image
import io
import uuid

_supabase_client: Client = None

def get_supabase_client():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
        
    url = os.environ.get('SUPABASE_URL', '').strip().strip('"').strip("'").rstrip('/')
    # Remove /rest/v1 if the user accidentally pasted the full API endpoint
    if url.endswith('/rest/v1'):
        url = url[:-8].rstrip('/')
        
    key = os.environ.get('SUPABASE_KEY', '').strip().strip('"').strip("'")
    
    if not url or not key:
        raise ValueError("SUPABASE_URL or SUPABASE_KEY missing in environment variables.")
        
    try:
        _supabase_client = create_client(url, key)
    except Exception as e:
        key_preview = key[:15] + "..." if len(key) > 15 else key
        raise ValueError(f"{str(e)} | Key starts with: '{key_preview}'")
        
    return _supabase_client

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
    try:
        supabase = get_supabase_client()
    except Exception as e:
        print(f"DEBUG: Supabase client initialization failed: {e}")
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
    Returns (public_url, error_message).
    """
    try:
        supabase = get_supabase_client()
    except Exception as e:
        return None, f"Supabase Init Failed: {str(e)}"
        
    try:
        import base64
        import uuid
        
        mime_type = "image/jpeg"
        ext = "jpg"
        
        if ',' in base64_str:
            prefix = base64_str.split(',')[0]
            base64_str = base64_str.split(',')[1]
            if 'image/png' in prefix:
                mime_type = 'image/png'
                ext = 'png'
            elif 'image/webp' in prefix:
                mime_type = 'image/webp'
                ext = 'webp'
                
        # Fix padding if necessary
        missing_padding = len(base64_str) % 4
        if missing_padding:
            base64_str += '=' * (4 - missing_padding)
        
        img_data = base64.b64decode(base64_str)
        filename = f"{uuid.uuid4()}.{ext}"
        full_path = f"{path.strip('/')}/{filename}"
        
        res = supabase.storage.from_(bucket).upload(
            path=full_path,
            file=img_data,
            file_options={"content-type": mime_type, "x-upsert": "true"}
        )
        return supabase.storage.from_(bucket).get_public_url(full_path), None
    except Exception as e:
        print(f"ERROR: Base64 upload failed: {e}")
        return None, str(e)

def delete_from_supabase_by_url(url, bucket="images"):
    """
    Attempts to extract path from public URL and delete from Supabase storage.
    """
    if not url:
        return False
    try:
        supabase = get_supabase_client()
        # Extract path from public URL
        # Format: https://[proj].supabase.co/storage/v1/object/public/[bucket]/[path]
        search_str = f"/storage/v1/object/public/{bucket}/"
        if search_str in url:
            path = url.split(search_str)[1]
            # Supabase API expects path relative to bucket
            supabase.storage.from_(bucket).remove([path])
            print(f"DEBUG: Successfully deleted from Supabase: {path}")
            return True
        return False
    except Exception as e:
        print(f"DEBUG: Supabase [DELETE ERROR]: {str(e)}")
        return False
