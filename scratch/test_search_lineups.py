from backend.rag_engine import rag_engine

def test_search():
    q = "Germany vs Curacao 14 Jun 2026 starting lineup"
    print("Searching for:", q)
    results = rag_engine.web_search_fallback(q, max_results=5)
    for idx, r in enumerate(results):
        print(f"\n[{idx+1}] Title: {r['title']}")
        print(f"    URL: {r['href']}")
        print(f"    Body: {r['body']}")

if __name__ == "__main__":
    test_search()
