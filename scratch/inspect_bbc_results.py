import requests
from bs4 import BeautifulSoup
import ssl

url = "https://www.bbc.com/sport/football/scores-fixtures"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

try:
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    print(f"Page title: {soup.title.string if soup.title else 'No title'}")
    
    # Search for common team names in results
    print("Searching for team names in elements...")
    for tag in ['span', 'div', 'p', 'a']:
        els = soup.find_all(tag)
        for el in els:
            text = el.get_text().strip()
            if any(name in text for name in ["City", "United", "Chelsea", "Arsenal", "Scotland", "England", "Spain"]):
                print(f"Tag: {tag}, Text: {text[:50]}, Classes: {el.get('class')}")
                break
                
    print("\nPrinting all elements with classes containing 'team' or 'score' or 'match'...")
    for tag in ['span', 'div', 'p', 'a']:
        els = soup.find_all(tag, class_=True)
        count = 0
        for el in els:
            cls_str = " ".join(el.get('class'))
            if any(k in cls_str.lower() for k in ['team', 'score', 'match', 'fixture']):
                print(f"Tag: {tag}, Class: {cls_str}, Text: {el.get_text().strip()[:100]}")
                count += 1
                if count > 20:
                    break
except Exception as e:
    print(f"Error: {e}")
