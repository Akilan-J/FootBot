import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_featured_matches():
    print("--- Testing GET /featured-matches ---")
    res = requests.get(f"{BASE_URL}/featured-matches")
    print("Status:", res.status_code)
    assert res.status_code == 200, "Failed to fetch featured matches"
    data = res.json()
    print("Featured Matches keys:", list(data.keys()))
    for key, val in data.items():
        print(f" - {key}: {val['home']} vs {val['away']} ({val['league']}) - Status: {val['status']}")
    assert "arg_fra" in data
    assert "upcoming" in data

def test_roster_completed_match():
    print("\n--- Testing GET /roster for completed match (Argentina vs France) ---")
    params = {
        "team_name": "Argentina",
        "opponent_name": "France",
        "match_date": "18 Dec 2022",
        "home_score": 3,
        "away_score": 3
    }
    res = requests.get(f"{BASE_URL}/roster", params=params)
    print("Status:", res.status_code)
    assert res.status_code == 200
    data = res.json()
    print("Roster status:", data.get("status"))
    print("Roster length:", len(data.get("roster", [])))
    print("Stats returned:", data.get("stats"))
    print("Events returned count:", len(data.get("events", [])))
    
    assert data.get("status") == "success"
    assert data.get("stats") is not None
    assert "possession" in data["stats"]
    assert "predicted_score" in data["stats"]

def test_roster_upcoming_match():
    print("\n--- Testing GET /roster for upcoming match (Liverpool vs PSG) ---")
    params = {
        "team_name": "Liverpool",
        "opponent_name": "PSG",
        "match_date": "16 Jun 2026",
        "home_score": 0,
        "away_score": 0
    }
    res = requests.get(f"{BASE_URL}/roster", params=params)
    print("Status:", res.status_code)
    assert res.status_code == 200
    data = res.json()
    print("Roster status:", data.get("status"))
    print("Roster length:", len(data.get("roster", [])))
    print("Stats (Predicted) returned:", data.get("stats"))
    
    assert data.get("status") == "success"
    assert data.get("stats") is not None
    assert "possession" in data["stats"]
    assert "predicted_score" in data["stats"]
    print("Predicted score for future match:", data["stats"]["predicted_score"])

def test_roster_fallback_squad():
    print("\n--- Testing GET /roster fallback for obscure team names (Fictional FC) ---")
    params = {
        "team_name": "Fictional FC",
        "opponent_name": "Obscure City",
        "match_date": "01 Jan 2026"
    }
    res = requests.get(f"{BASE_URL}/roster", params=params)
    print("Status:", res.status_code)
    assert res.status_code == 200
    data = res.json()
    print("Roster status:", data.get("status"))
    print("Roster length:", len(data.get("roster", [])))
    print("First player in roster:", data.get("roster", [])[0] if data.get("roster") else None)
    
    assert data.get("status") == "success"
    assert len(data.get("roster", [])) == 11
    assert data.get("stats") is not None

if __name__ == "__main__":
    try:
        test_featured_matches()
        test_roster_completed_match()
        test_roster_upcoming_match()
        test_roster_fallback_squad()
        print("\n🎉 ALL DYNAMIC STATS ENDPOINT TESTS PASSED SUCCESSFULLY!")
    except AssertionError as e:
        print("\n❌ TEST FAILED:", e)
        sys.exit(1)
    except Exception as e:
        print("\n🚨 ERROR RUNNING TESTS:", e)
        sys.exit(1)
