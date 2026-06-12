import sys
from pathlib import Path

# Setup python path to include the current workspace
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.roster_store import resolve_fotmob_id, download_image

def main():
    players_to_replace = [
        {"name": "Ederson", "team": "Manchester City", "filename": "ederson.png"},
        {"name": "Rúben Dias", "team": "Manchester City", "filename": "dias.png"},
        {"name": "Rodri", "team": "Manchester City", "filename": "rodri.png"},
        {"name": "Bernardo Silva", "team": "Manchester City", "filename": "silva.png"},
        {"name": "Kevin De Bruyne", "team": "Manchester City", "filename": "debruyne.png"},
        {"name": "Phil Foden", "team": "Manchester City", "filename": "foden.png"},
        {"name": "Erling Haaland", "team": "Manchester City", "filename": "haaland.png"},
        {"name": "Jude Bellingham", "team": "Real Madrid", "filename": "bellingham.jpg"},
    ]

    assets_dir = Path(__file__).resolve().parent.parent / "frontend" / "assets"
    
    print("Resolving and replacing old images with FotMob CDN versions...")
    for p in players_to_replace:
        name = p["name"]
        team = p["team"]
        filename = p["filename"]
        
        print(f"\nResolving FotMob ID for {name} ({team})...")
        fotmob_id = resolve_fotmob_id(name, team)
        if fotmob_id:
            url = f"https://images.fotmob.com/image_resources/playerimages/{fotmob_id}.png"
            dest_path = assets_dir / filename
            print(f"Downloading from {url} to {dest_path}...")
            success = download_image(url, dest_path)
            if success:
                print(f"Successfully replaced {filename} with FotMob version!")
            else:
                print(f"Failed to download image for {name}")
        else:
            print(f"Could not resolve FotMob ID for {name}")

if __name__ == "__main__":
    main()
