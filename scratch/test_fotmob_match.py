import requests
import json

def fetch_details(match_id):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    
    urls = [
        f"https://www.fotmob.com/api/matchDetails?matchId={match_id}",
        f"https://apigw.fotmob.com/application/api/matchDetails?matchId={match_id}",
        f"https://apigw.fotmob.com/application/api/matchDetails?id={match_id}",
        f"https://www.fotmob.com/api/matchdetails?matchId={match_id}",
    ]
    
    for url in urls:
        print(f"Trying URL: {url}")
        try:
            r = requests.get(url, headers=headers, timeout=5)
            print(f"  Status code: {r.status_code}")
            if r.status_code == 200:
                print("  SUCCESS!")
                data = r.json()
                print("  Content keys:", data.get("content", {}).keys())
                # Save a sample to test
                with open("scratch/sample_match.json", "w") as f:
                    json.dump(data, f, indent=2)
                return True
        except Exception as e:
            print(f"  Error: {e}")
    return False

if __name__ == '__main__':
    fetch_details("4667777")
