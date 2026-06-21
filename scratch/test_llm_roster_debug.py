import logging
import json
import sys
import requests
from bs4 import BeautifulSoup

from backend.roster_store import get_real_world_roster
from backend.rag_engine import rag_engine

# Force debug logging
logger = logging.getLogger("footbot")
logger.setLevel(logging.DEBUG)

team_name = "Congo DR"
opponent_name = "Portugal"
search_date = "17 June 2026"

q1 = f"{team_name} vs {opponent_name} {search_date} starting XI"
q2 = f"{team_name} vs {opponent_name} {search_date} lineups"

r1 = rag_engine.web_search_fallback(q1, max_results=3, clean=False)
r2 = rag_engine.web_search_fallback(q2, max_results=3, clean=False)

seen = set()
search_results = []
for r in r1 + r2:
    href = r.get("href", "")
    if href and href in seen:
        continue
    if href:
        seen.add(href)
    search_results.append(r)

print("Yahoo Search results found:")
for r in search_results:
    print("- Title:", r["title"], "Url:", r["href"])

search_context_parts = []
for r in search_results:
    search_context_parts.append(f"- {r['title']}: {r['body']}")

for r in search_results:
    url = r.get("href", "")
    if url and not any(loc in url for loc in ["localhost", "127.0.0.1"]):
        print(f"Fetching webpage content for: {url}")
        try:
            page_res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5.0)
            if page_res.status_code == 200:
                page_soup = BeautifulSoup(page_res.text, "html.parser")
                for s in page_soup(["script", "style", "noscript", "header", "footer", "nav"]):
                    s.extract()
                page_text = page_soup.get_text(separator=" ")
                cleaned = " ".join([phrase.strip() for phrase in page_text.split() if phrase.strip()])
                print(f"  Fetched {len(cleaned)} chars. Snippet: {cleaned[:300]}")
                search_context_parts.append(f"\n--- Page: {url} ---\n{cleaned[:6000]}")
        except Exception as e:
            print("  Error:", e)

context = "\n".join(search_context_parts)
print("\n--- Context length:", len(context))
# Check if key players are in context
for name in ["Mpasi", "Wan-Bissaka", "Bakambu", "Wissa", "Gaston", "Bolasie"]:
    print(f"Is '{name}' in context?", name.lower() in context.lower())
