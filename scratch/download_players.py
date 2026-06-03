import urllib.request
import os
import ssl

assets_dir = "/Users/akilan/Documents/FootBot/FootBot/frontend/assets"
os.makedirs(assets_dir, exist_ok=True)

players = {
    "bellingham": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/25th_Laureus_World_Sports_Awards_-_Red_Carpet_-_Jude_Bellingham_-_240422_190551-2_%28cropped%29.jpg/500px-25th_Laureus_World_Sports_Awards_-_Red_Carpet_-_Jude_Bellingham_-_240422_190551-2_%28cropped%29.jpg"
}

headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}

# Bypass SSL verification
context = ssl._create_unverified_context()

for name, url in players.items():
    try:
        print(f"Downloading {name} from {url}...")
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=context) as response:
            ext = "jpg"
            dest = os.path.join(assets_dir, f"{name}.{ext}")
            with open(dest, 'wb') as f:
                f.write(response.read())
        print(f"Successfully downloaded {name} to {dest}")
    except Exception as e:
        print(f"Failed to download {name}: {e}")
