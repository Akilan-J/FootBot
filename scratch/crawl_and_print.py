import logging
from backend.database import save_historical_match, get_historical_matches
from backend.loaders.live_score_loader import fetch_historical_results_from_html

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def crawl_and_inspect():
    print("Fetching matches from BBC Sport...")
    crawled_matches = fetch_historical_results_from_html()
    print(f"Crawled {len(crawled_matches)} matches.")
    
    before_matches = get_historical_matches(limit=100)
    before_map = {(m["home_team"].lower(), m["away_team"].lower()): m for m in before_matches}
    
    updates = 0
    new_inserts = 0
    
    for m in crawled_matches:
        home = m["home_team"]
        away = m["away_team"]
        hs = m["home_score"]
        as_val = m["away_score"]
        date = m["match_date"]
        league = m["league"]
        
        # Check if match exists in DB
        key = (home.lower(), away.lower())
        exist = before_map.get(key)
        
        save_historical_match(home, away, hs, as_val, date, league)
        
        if exist:
            if exist["home_score"] != hs or exist["away_score"] != as_val:
                print(f"UPDATE: {home} vs {away} was {exist['home_score']}-{exist['away_score']}, now {hs}-{as_val}")
                updates += 1
        else:
            print(f"NEW MATCH: {home} {hs}-{as_val} {away} on {date}")
            new_inserts += 1
            
    print(f"Crawl finished. Updates: {updates}, New Inserts: {new_inserts}")

if __name__ == "__main__":
    crawl_and_inspect()
