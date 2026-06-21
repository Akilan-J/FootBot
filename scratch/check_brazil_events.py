import json
import logging
from backend.roster_store import get_match_events, load_cache

logging.basicConfig(level=logging.INFO)

# Let's inspect the cached values first
cache = load_cache()
for k, v in cache.items():
    if "brazil" in k and "haiti" in k:
        print(f"Cache key: {k}")
        print(f"Cache value: {json.dumps(v, indent=2)}")

# Let's fetch using the API
events = get_match_events("Brazil", "Haiti", "20 Jun 2026")
print("\nReturned Events:")
print(json.dumps(events, indent=2))
