import requests
from bs4 import BeautifulSoup
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

def test_match_web_page(match_id, slug):
    url = f"https://www.fotmob.com/matches/{slug}/{match_id}"
    print(f"Fetching match web page: {url}")
    r = requests.get(url, headers=headers)
    print("Status:", r.status_code)
    if r.status_code == 200:
        html = r.text
        soup = BeautifulSoup(html, "html.parser")
        next_data = soup.find("script", id="__NEXT_DATA__")
        if next_data:
            print("FOUND __NEXT_DATA__!")
            data = json.loads(next_data.string)
            # Save the NextData to inspect
            with open("scratch/web_page_next_data.json", "w") as f:
                json.dump(data, f, indent=2)
                
            # Search for lineup in the page props
            props = data.get("props", {})
            page_props = props.get("pageProps", {})
            fallback = page_props.get("fallback", {})
            
            found_lineup = False
            for key, val in fallback.items():
                if "lineup" in key.lower() or "lineup" in str(val).lower():
                    print(f"Lineup info found in fallback key: {key}")
                    found_lineup = True
                    # Let's save a snippet of this key's content
                    with open("scratch/lineup_data_snippet.json", "w") as sf:
                        json.dump(val, sf, indent=2)
            
            if not found_lineup:
                print("Lineup info NOT found in fallback props.")
        else:
            print("No __NEXT_DATA__ found.")
    else:
        print("Failed to fetch web page:", r.text[:200])

if __name__ == "__main__":
    # Test Germany vs Scotland (4043837, slug: germany-vs-scotland)
    test_match_web_page("4043837", "germany-vs-scotland")
