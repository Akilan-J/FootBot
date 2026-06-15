import requests
from bs4 import BeautifulSoup
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

def test_html_content():
    url = "https://www.fotmob.com/matchDetails?matchId=4043837"
    r = requests.get(url, headers=headers)
    print("Status:", r.status_code)
    print("Content Type:", r.headers.get("Content-Type"))
    
    html = r.text
    print("HTML length:", len(html))
    
    # Save a snippet
    with open("scratch/match_details_page.html", "w") as f:
        f.write(html)
        
    soup = BeautifulSoup(html, "html.parser")
    # Search for json/data in scripts (e.g. __NEXT_DATA__)
    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data:
        print("FOUND __NEXT_DATA__!")
        data = json.loads(next_data.string)
        print("Keys in __NEXT_DATA__:", data.keys())
        # Save JSON
        with open("scratch/next_data.json", "w") as f:
            json.dump(data, f, indent=2)
            
        # Check if lineups are in the next data
        props = data.get("props", {})
        page_props = props.get("pageProps", {})
        fallback = page_props.get("fallback", {})
        print("Fallback keys:", list(fallback.keys())[:5])
        
        # Let's inspect the keys to see if lineup data is present
        for key in fallback:
            if "matchDetails" in key or "lineup" in key:
                print(f"Match details key found: {key}")
                match_details = fallback[key]
                print("Match details type:", type(match_details))
                if isinstance(match_details, dict):
                    print("Match details keys:", match_details.keys())
                    content = match_details.get("content", {})
                    print("Content keys:", content.keys())
                    lineup = content.get("lineup", {})
                    print("Lineup keys:", lineup.keys())
    else:
        print("No __NEXT_DATA__ script found.")

if __name__ == "__main__":
    test_html_content()
