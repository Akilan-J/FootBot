import json
import sqlite3
from pathlib import Path

def check_cache():
    cache_path = Path("data/roster_cache.json")
    if not cache_path.exists():
        print("No cache file found.")
        return
        
    with open(cache_path, "r", encoding="utf-8") as f:
        cache = json.load(f)
        
    print(f"Total cache keys: {len(cache)}")
    
    conn = sqlite3.connect("data/footbot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT home_team, away_team, match_date FROM historical_matches;")
    matches = cursor.fetchall()
    conn.close()
    
    print(f"Total database matches: {len(matches)}")
    print("\nStatus of database matches in cache:")
    
    import unicodedata
    import re
    
    def normalize_name(name):
        n = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('utf-8')
        n = n.lower().strip()
        n = re.sub(r"\s+u\d+\b", "", n)
        n = re.sub(r"\s+u-\d+\b", "", n)
        return n
        
    uncached = []
    
    for home, away, date in matches:
        norm_home = normalize_name(home)
        norm_away = normalize_name(away)
        norm_date = date.lower().strip()
        
        key_home = f"{norm_home}_vs_{norm_away}_{norm_date}"
        key_away = f"{norm_away}_vs_{norm_home}_{norm_date}"
        
        cached_home = key_home in cache
        cached_away = key_away in cache
        
        print(f" - {home} vs {away} ({date}): "
              f"Home Cached: {cached_home}, Away Cached: {cached_away}")
        
        if not cached_home:
            uncached.append((home, away, date))
        if not cached_away:
            uncached.append((away, home, date))
            
    print(f"\nUncached match teams: {len(uncached)}")

if __name__ == "__main__":
    check_cache()
