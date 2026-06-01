import urllib.request

urls = [
    "https://cdn.jsdelivr.net/npm/@vladmandic/human/model/faceres.json",
    "https://cdn.jsdelivr.net/npm/@vladmandic/human/models/faceres.json",
    "https://cdn.jsdelivr.net/gh/vladmandic/human-models/models/faceres.json"
]

for url in urls:
    print(f"Testing URL: {url}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            print(f"-> Success! Status code: {status}")
    except Exception as e:
        print(f"-> Failed! Error: {e}")
