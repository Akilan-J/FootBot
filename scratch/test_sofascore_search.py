from duckduckgo_search import DDGS

def search_match_url():
    query = '"Germany" "Curacao" site:fotmob.com'
    print(f"Searching for: {query}")
    with DDGS() as ddgs:
        results = ddgs.text(query, max_results=5)
        for idx, r in enumerate(results):
            print(f"\n[{idx+1}] Title: {r.get('title')}")
            print(f"    URL: {r.get('href')}")
            print(f"    Snippet: {r.get('body')}")

if __name__ == "__main__":
    search_match_url()
