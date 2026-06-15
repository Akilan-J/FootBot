import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_germany_curacao_lineup():
    print("--- Testing Germany vs Curacao Lineup Fetch ---")
    url = f"{BASE_URL}/roster"
    params = {
        "team_name": "Germany",
        "opponent_name": "Curacao",
        "match_date": "14 Jun 2026"
    }
    
    r = requests.get(url, params=params)
    print("Status Code:", r.status_code)
    assert r.status_code == 200, "Roster request failed"
    
    data = r.json()
    print("Response Status:", data.get("status"))
    roster = data.get("roster", [])
    print(f"Roster size: {len(roster)}")
    
    # Print the resolved starting XI players
    for p in roster:
        print(f" - {p.get('jersey')}. {p.get('name')} ({p.get('pos')}) - Rating: {p.get('rating')}")

if __name__ == "__main__":
    test_germany_curacao_lineup()
