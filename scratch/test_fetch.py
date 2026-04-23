import requests

url = "https://yjalvcyjavobqlrrkpyw.supabase.co/storage/v1/object/public/images/gallery/images%20(1).jpeg"
try:
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    print(f"Content Type: {response.headers.get('Content-Type')}")
    print(f"Content Length: {len(response.content)}")
except Exception as e:
    print(f"Error: {e}")
