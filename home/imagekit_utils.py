import base64
from imagekitio import ImageKit
from django.conf import settings

# Initialize ImageKit
# Using provided keys and endpoint
imagekit = ImageKit(
    public_key="public_t9vvNeEKiVs9c7CpHjKHek0V+Aw=",
    private_key="private_qXEUvhHsNdmxrM8AqiEZzlfUg3s=",
    url_endpoint="https://ik.imagekit.io/anlsbeoqrq"
)

def upload_to_imagekit(file_obj, folder="/user_uploads"):
    """
    Uploads a file object to ImageKit.
    Returns the file URL if successful, else None.
    """
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
        # It's important to re-raise or at least return None so the view knows it failed
        return None
