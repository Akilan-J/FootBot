import json
import logging
from backend.roster_store import get_match_events, load_cache, save_cache

logging.basicConfig(level=logging.INFO)

cache = load_cache()
key = "matchevents_brazil_vs_haiti_20 jun 2026"
if key in cache:
    print(f"Deleting bad cache key: {key}")
    del cache[key]
    save_cache(cache)

print("Fetching fresh events via RAG...")
events = get_match_events("Brazil", "Haiti", "20 Jun 2026")
print("\nNew Cached Events:")
print(json.dumps(events, indent=2))
