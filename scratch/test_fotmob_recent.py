import requests
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

def test_recent_match():
    # Search for Germany vs Scotland
    query = "Germany vs Scotland"
    url = f"https://apigw.fotmob.com/searchapi/suggest?term={query}&lang=en"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        options = []
        for val in data.values():
            if isinstance(val, list):
                for group in val:
                    if isinstance(group, dict) and "options" in group:
                        options.extend(group["options"])
        for opt in options:
            text = opt.get("text")
            payload = opt.get("payload", {})
            mid = payload.get("id")
            if mid:
                print(f"Found match: {text} -> ID: {mid} -> Date: {payload.get('matchDate')}")
                # Fetch details
                details_url = f"https://www.fotmob.com/api/matchDetails?matchId={mid}"
                print(f"Fetching details from: {details_url}")
                r_det = requests.get(details_url, headers=headers)
                print(f"Details status: {r_det.status_code}")
                if r_det.status_code == 200:
                    details_data = r_det.json()
                    print("Lineups available:", "lineup" in details_data.get("content", {}))
                    # Print lineup keys or first few players
                    lineup = details_data.get("content", {}).get("lineup", {})
                    print("Lineup keys:", lineup.keys())
                    break
                else:
                    print("Failed to get match details:", r_det.text[:200])

if __name__ == "__main__":
    test_recent_match()
