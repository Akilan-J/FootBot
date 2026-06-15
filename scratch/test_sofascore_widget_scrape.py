import requests
from bs4 import BeautifulSoup
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

def test_widget_fetch(match_id):
    url = f"https://widgets.sofascore.com/embed/lineups?id={match_id}&widgetTheme=dark"
    print(f"Fetching widget page: {url}")
    try:
        r = requests.get(url, headers=headers)
        print("Status:", r.status_code)
        if r.status_code == 200:
            html = r.text
            print("HTML Length:", len(html))
            # Save HTML
            with open("scratch/widget_response.html", "w") as f:
                f.write(html)
            
            # Let's search for some players or keywords in HTML
            # e.g. Messi or other players from Argentina vs Iceland (11352348)
            print("Contains 'Messi':", "Messi" in html)
            print("Contains 'Iceland':", "Iceland" in html)
            print("Contains 'Lineups':", "Lineups" in html or "lineups" in html)
            
            # Print a snippet of HTML around any scripts
            soup = BeautifulSoup(html, 'html.parser')
            scripts = soup.find_all('script')
            print("Found scripts:", len(scripts))
            for i, s in enumerate(scripts):
                src = s.get('src')
                content = s.string or ""
                if src:
                    print(f"Script {i}: src={src}")
                else:
                    print(f"Script {i}: length={len(content)}, snippet={content[:200]}")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    # Argentina vs Iceland ID: 11352348
    test_widget_fetch("11352348")
