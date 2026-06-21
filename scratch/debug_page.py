import requests
from bs4 import BeautifulSoup

url = "https://www.futbol24.com/match/2026/06/17/international/FIFA/World-Cup/2026/Group-K/Portugal/vs/DR-Congo/"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
}
try:
    r = requests.get(url, headers=headers, timeout=10.0)
    print("Status Code:", r.status_code)
    print("Content length:", len(r.content))
    print("Text length:", len(r.text))
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text()
    print("Text content sample:", repr(text[:200]))
except Exception as e:
    print("Error:", e)
