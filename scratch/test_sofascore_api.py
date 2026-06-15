import requests

def test_sofascore():
    # Let's try requesting a Sofascore lineups URL using event ID "dLsxhd"
    url = "https://api.sofascore.com/api/v1/event/dLsxhd/lineups"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Referer": "https://www.sofascore.com/"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print("Status Code:", r.status_code)
        if r.status_code == 200:
            print("Success! Response JSON:")
            data = r.json()
            print(data.keys())
        else:
            print("Failed. Response text:", r.text[:200])
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_sofascore()
