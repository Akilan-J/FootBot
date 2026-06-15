import requests
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
}

def test_search(query):
    url = f"https://apigw.fotmob.com/searchapi/suggest?term={query}&lang=en"
    print(f"Searching for: {query}")
    r = requests.get(url, headers=headers)
    print("Status:", r.status_code)
    if r.status_code == 200:
        data = r.json()
        print(json.dumps(data, indent=2)[:2000]) # Print first 2000 chars of response

if __name__ == "__main__":
    test_search("Germany vs Curacao")
    test_search("Germany Curacao")
