import requests

def test_fotmob_match():
    # Let's test a known match ID or search for a match
    # First, let's try calling matchDetails API directly
    # A typical match ID for a recent/upcoming match: let's try to fetch a random match detail
    url = "https://www.fotmob.com/api/matchDetails"
    params = {"matchId": "4822452"} # Example match ID (just a random ID)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "x-fm-req": "true"
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        print("Status Code:", r.status_code)
        if r.status_code == 200:
            print("Success! Response JSON structure:")
            data = r.json()
            print(list(data.keys()))
            if "content" in data:
                print("content keys:", list(data["content"].keys()))
                if "lineup" in data["content"]:
                    print("lineup keys:", list(data["content"]["lineup"].keys()))
        else:
            print("Failed. Response text:", r.text[:200])
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_fotmob_match()
