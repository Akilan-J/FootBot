import requests

BASE_URL = "http://127.0.0.1:8000"

def test_live_roster():
    print("--- Testing GET /roster for Today match ---")
    params = {
        "team_name": "Portugal",
        "opponent_name": "Congo DR",
        "match_date": "Today",
        "home_score": 1,
        "away_score": 1
    }
    res = requests.get(f"{BASE_URL}/roster", params=params)
    print("Status:", res.status_code)
    assert res.status_code == 200, "Roster fetch failed"
    data = res.json()
    print("Roster status:", data.get("status"))
    print("Roster length:", len(data.get("roster", [])))
    print("Stats:", data.get("stats"))
    print("Events:", data.get("events"))

if __name__ == "__main__":
    test_live_roster()
