import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

def test_permutations():
    match_id = "4043837" # Germany vs Scotland
    urls = [
        f"https://www.fotmob.com/api/matchDetails?id={match_id}",
        f"https://www.fotmob.com/api/matchDetails?matchId={match_id}",
        f"https://www.fotmob.com/api/matchdetails?id={match_id}",
        f"https://www.fotmob.com/api/matchdetails?matchId={match_id}",
        f"https://apigw.fotmob.com/application/api/matchDetails?id={match_id}",
        f"https://apigw.fotmob.com/application/api/matchDetails?matchId={match_id}",
        f"https://apigw.fotmob.com/application/api/matchdetails?id={match_id}",
        f"https://apigw.fotmob.com/application/api/matchdetails?matchId={match_id}",
    ]
    for url in urls:
        print(f"Trying URL: {url}")
        try:
            r = requests.get(url, headers=headers, timeout=5)
            print(f"  Status code: {r.status_code}")
            if r.status_code == 200:
                print("  SUCCESS!")
                print("  Content preview:", r.text[:300])
                break
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    test_permutations()
