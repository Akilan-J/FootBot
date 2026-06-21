import logging
import json
import sys
import requests
from bs4 import BeautifulSoup

from backend.roster_store import normalize_name, normalize_date_string, _clean_yahoo_url
from backend.rag_engine import rag_engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

home = "Portugal"
away = "Congo DR"
resolved_date = "17 Jun 2026"

search_query = f"{home} vs {away} {resolved_date} goalscorers assists goals score"
print("Search query:", search_query)
search_results = rag_engine.web_search_fallback(search_query, max_results=5, clean=False)

search_context_parts = []
team_keywords = []
for team in [home, away]:
    t_norm = normalize_name(team)
    team_keywords.append(t_norm)
    for word in t_norm.split():
        if len(word) > 3:
            team_keywords.append(word)
if any(x in team_keywords for x in ["congo dr", "congo"]):
    team_keywords.extend(["congo", "dr congo", "drc"])

keywords = team_keywords + ["goal", "assist", "score", "minute", "scorer", "penalty", "own goal", "ht", "ft", "neves", "wissa"]

for idx, r in enumerate(search_results):
    url = r.get("href", "")
    if url:
        url = _clean_yahoo_url(url)
    print(f"\n--- URL #{idx}: {url} ---")
    if url:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            page_res = requests.get(url, headers=headers, timeout=5.0)
            if page_res.status_code == 200:
                soup = BeautifulSoup(page_res.text, "html.parser")
                text_content = soup.get_text(separator="\n")
                lines = [l.strip() for l in text_content.splitlines() if l.strip()]
                relevant_sentences = []
                for line in lines:
                    if any(k in line.lower() for k in keywords) and len(line) < 300:
                        relevant_sentences.append(line)
                
                filtered_text = " ".join(relevant_sentences)[:2000]
                print(f"Filtered text len: {len(filtered_text)}")
                print(f"Snippet: {filtered_text[:600]}")
                if filtered_text:
                    search_context_parts.append(f"[Webpage Content from {url}]:\n{filtered_text}")
        except Exception as e:
            print("Error fetching:", e)

search_context = "\n\n".join(search_context_parts)

prompt = f"""You are a professional football database helper. Your job is to extract the actual, real-world goal events (goalscorers and assists) for the match: '{home}' vs '{away}' played on '{resolved_date}'.

Here is the search context containing match reports, commentaries, or summaries:
{search_context}

Using the search context above, return a JSON list of all actual goals scored during the match.
Each goal event in the list must be a JSON object with exactly the following keys:
- 'minute': the minute of the goal (e.g. "12'" or "45+2'")
- 'scorer': the full name of the goalscorer
- 'assist': the full name of the player who assisted the goal (or null if unassisted)
- 'team': the exact team name who scored (either '{home}' or '{away}')
- 'ownGoal': true if it was own goal, false otherwise
- 'penalty': true if it was penalty, false otherwise
- 'text': a short description of the goal

Important Rules:
1. Do NOT make up, predict, or estimate any goals. Extract ONLY the actual goals that occurred as documented in the search context.
2. If the match has not happened yet, or if no goal details are found in the search context, return an empty JSON array [].
3. Ensure the team names match exactly '{home}' or '{away}'.
4. Return ONLY a raw valid JSON array. Do not write any markdown code wrappers, explanations, or notes."""

if rag_engine.openai_client is not None:
    try:
        completion = rag_engine.openai_client.chat.completions.create(
            model=rag_engine.model_name,
            messages=[
                {"role": "system", "content": "You are a database system returning raw JSON arrays only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            timeout=15.0
        )
        print("\n=== LLM Response ===")
        print(completion.choices[0].message.content)
    except Exception as e:
        print("LLM Error:", e)
