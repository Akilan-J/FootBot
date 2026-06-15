import requests
import urllib.parse

def search_sofascore():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    
    # Try searching for Germany vs Curacao
    query = "Germany Curacao"
    url = f"https://www.sofascore.com/api/v1/search/all?q={urllib.parse.quote_plus(query)}"
    
    r = requests.get(url, headers=headers)
    print(f"Status code: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print("Results:")
        for key, val in data.items():
            if isinstance(val, list):
                print(f"Key '{key}' count: {len(val)}")
                for item in val[:5]:
                    print(f"  {item}")
    else:
        print("Failed search request:", r.text[:200])

if __name__ == '__main__':
    search_sofascore()
