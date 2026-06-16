import json
import requests
import sqlite3
import os

CACHE_PATH = "data/roster_cache.json"
BASE_URL = "http://127.0.0.1:8000"

def clean_cache():
    if not os.path.exists(CACHE_PATH):
        print("Roster cache not found.")
        return
        
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        cache = json.load(f)
        
    print(f"Loaded cache with {len(cache)} keys.")
    
    # We want to clear match-specific roster, stats, and event keys for World Cup matches to trigger fresh fetching.
    # We keep standard team keys (like general club squads) but clear match-specific keys (containing "_vs_")
    # that are from 2026 or have generic/hallucinated rosters.
    keys_to_clear = []
    for k in cache.keys():
        if "_vs_" in k:
            # Clear all 2026 and today match rosters, stats, and events
            if "2026" in k or "today" in k or "jun" in k:
                keys_to_clear.append(k)
                
    print(f"Clearing {len(keys_to_clear)} match keys from cache...")
    for k in keys_to_clear:
        del cache[k]
        print(f" - Deleted: {k}")
        
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=4)
        
    print("Cache updated successfully.")

def trigger_resolution():
    # Fetch all historical matches from SQLite database
    conn = sqlite3.connect("data/footbot.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT home_team, away_team, match_date, home_score, away_score FROM historical_matches")
    matches = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    print(f"Found {len(matches)} matches in database to trigger.")
    
    for m in matches:
        home = m["home_team"]
        away = m["away_team"]
        date = m["match_date"]
        hs = m["home_score"]
        as_score = m["away_score"]
        
        # We only care about Allowed leagues or World Cup matches (avoid friendlies/others if needed, but let's do all)
        print(f"\nTriggering roster resolution for: {home} vs {away} ({date})...")
        
        # 1. Trigger Home Roster
        try:
            home_url = f"{BASE_URL}/roster"
            params = {
                "team_name": home,
                "opponent_name": away,
                "match_date": date,
                "home_score": hs,
                "away_score": as_score
            }
            print(f" -> Querying home team roster...")
            res = requests.get(home_url, params=params, timeout=120)
            if res.ok:
                print(f" -> Success! Response status: {res.json().get('status')}")
            else:
                print(f" -> Failed: {res.status_code} {res.text}")
        except Exception as e:
            print(f" -> Error: {e}")
            
        # 2. Trigger Away Roster
        try:
            away_url = f"{BASE_URL}/roster"
            params = {
                "team_name": away,
                "opponent_name": home,
                "match_date": date
            }
            print(f" -> Querying away team roster...")
            res = requests.get(away_url, params=params, timeout=120)
            if res.ok:
                print(f" -> Success! Response status: {res.json().get('status')}")
            else:
                print(f" -> Failed: {res.status_code} {res.text}")
        except Exception as e:
            print(f" -> Error: {e}")

if __name__ == "__main__":
    clean_cache()
    trigger_resolution()
