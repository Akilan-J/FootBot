import sys
import os
import json
from pathlib import Path

# Setup python path to include the current workspace
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.roster_store import get_real_world_roster, PREDEFINED_ROSTERS, load_cache, save_cache, ensure_player_photos

def main():
    print("Pre-downloading all player headshots from FotMob...")
    
    # 1. Process PREDEFINED_ROSTERS
    # PREDEFINED_ROSTERS is a dictionary. When we retrieve team rosters, they get cached.
    # Let's resolve the rosters for all predefined teams.
    for team_name in PREDEFINED_ROSTERS.keys():
        print(f"\nProcessing predefined roster for: {team_name}")
        get_real_world_roster(team_name)
        
    # 2. Process all cached rosters in data/roster_cache.json
    cache = load_cache()
    print(f"\nProcessing cached rosters. Total teams in cache: {len(cache)}")
    for team_name, roster in cache.items():
        print(f"Processing cached roster for: {team_name}")
        # Call ensure_player_photos directly on the cached roster
        updated = ensure_player_photos(roster, team_name)
        if updated:
            cache[team_name] = roster
            
    # Save the updated cache
    save_cache(cache)
    print("\nAll player headshots preloaded successfully!")

if __name__ == "__main__":
    main()
