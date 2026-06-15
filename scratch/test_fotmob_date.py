import requests
import json

def fetch_matches_by_date(date_str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    url = f"https://www.fotmob.com/api/matches?date={date_str}"
    
    print(f"Fetching matches for date {date_str} from URL: {url}")
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"Status code: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            # Save data to debug
            with open("scratch/fotmob_date_matches.json", "w") as f:
                json.dump(data, f, indent=2)
            
            # Search for Germany or Curacao
            leagues = data.get("leagues", [])
            print(f"Leagues found: {len(leagues)}")
            found = False
            for league in leagues:
                for match in league.get("matches", []):
                    home = match.get("home", {}).get("name")
                    away = match.get("away", {}).get("name")
                    mid = match.get("id")
                    if "Germany" in (home or "") or "Curacao" in (home or "") or "Germany" in (away or "") or "Curacao" in (away or ""):
                        print(f"  FOUND MATCH: {home} vs {away} (ID: {mid})")
                        found = True
            if not found:
                print("  No matches matching Germany or Curacao found on this date.")
        else:
            print("Failed to fetch matches:", r.text[:200])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    fetch_matches_by_date("20260614")
