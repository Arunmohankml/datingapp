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
        # Read file content and encode to base64
        file_obj.seek(0)
        file_content = file_obj.read()
        
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
        
        if upload_response and upload_response.url:
            return upload_response.url
        return None
        
    except Exception as e:
        print(f"ImageKit Upload Error: {e}")
        return None
