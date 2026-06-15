import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

def test_endpoints():
    match_id = "4043837"
    urls = [
        f"https://apigw.fotmob.com/api/matchDetails?matchId={match_id}",
        f"https://apigw.fotmob.com/api/matchdetails?matchId={match_id}",
        f"https://apigw.fotmob.com/matchDetails?matchId={match_id}",
        f"https://apigw.fotmob.com/matchdetails?matchId={match_id}",
        f"https://www.fotmob.com/matchDetails?matchId={match_id}",
        f"https://www.fotmob.com/matchdetails?matchId={match_id}",
    ]
    for url in urls:
        print(f"Trying: {url}")
        try:
            r = requests.get(url, headers=headers, timeout=5)
            print(f"  Status: {r.status_code}")
            if r.status_code == 200:
                print("  SUCCESS!")
                print(r.text[:200])
                break
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    test_endpoints()
