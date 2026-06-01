import urllib.request

url = "https://cdn.jsdelivr.net/npm/@vladmandic/human/dist/human.js"
print("Downloading human.js from CDN...")
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as response:
    js_content = response.read().decode('utf-8')

print("Length of JS content:", len(js_content))

print("\nLast 2000 characters:")
print(js_content[-2000:])
