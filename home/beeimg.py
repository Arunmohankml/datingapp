import requests

def upload_to_beeimg(image_file):
    """
    Uploads an image file to BeeIMG using the public/anonymous API.
    Returns the URL of the uploaded image if successful, else None.
    """
    url = "https://beeimg.com/api/upload/file/json/"
    
    try:
        # Seek to start of file to ensure it's read from the beginning
        image_file.seek(0)
        
        files = {
            'image': (image_file.name, image_file, 'image/jpeg') # MIME type can be improved
        }
        
        response = requests.post(url, files=files, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            # BeeIMG response format for public upload usually contains 'files' or 'url'
            # Based on standard behavior, we look for data['url'] or data['files'][0]['url']
            if isinstance(data, dict):
                # Try common keys returned by such APIs
                return data.get('url') or data.get('link') or (data.get('files', [{}])[0].get('url') if data.get('files') else None)
        
        return None
    except Exception as e:
        print(f"BeeIMG upload error: {e}")
        return None
