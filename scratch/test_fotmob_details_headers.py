import requests

def test_headers():
    match_id = "4043837" # Germany vs Scotland (Euro 2024)
    url = f"https://www.fotmob.com/api/matchDetails?matchId={match_id}"
    
    headers_list = [
        # 1. Standard Chrome user agent
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
        # 2. Chrome with referer
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.fotmob.com/"
        },
        # 3. Minimal headers
        {
            "User-Agent": "Mozilla/5.0"
        }
    ]
    
    for i, headers in enumerate(headers_list):
        print(f"--- Attempt {i+1} ---")
        try:
            r = requests.get(url, headers=headers, timeout=5)
            print(f"Status Code: {r.status_code}")
            if r.status_code == 200:
                print("SUCCESS!")
                print("Content preview:", r.text[:300])
                return
            else:
                print("Response starts with:", r.text[:200])
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    test_headers()
