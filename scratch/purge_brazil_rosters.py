import json
import logging
from backend.roster_store import get_real_world_roster, load_cache, save_cache

logging.basicConfig(level=logging.INFO)

cache = load_cache()
keys_to_purge = ["brazil_vs_haiti_20 jun 2026", "haiti_vs_brazil_20 jun 2026"]
for key in keys_to_purge:
    if key in cache:
        print(f"Deleting cached roster: {key}")
        del cache[key]

save_cache(cache)

print("Fetching Brazil match squad with substitutes...")
brazil_roster = get_real_world_roster("Brazil", "Haiti", "20 Jun 2026")
print("\nBrazil Squad (Starters & Subs):")
for p in brazil_roster:
    sub_desc = f"Sub (in for {p.get('subbed_in_for')} at {p.get('subbed_in_minute')})" if p.get("sub") else "Starter"
    print(f" - #{p.get('jersey')} {p.get('name')} ({p.get('pos')}) - {sub_desc}")

print("\nFetching Haiti match squad with substitutes...")
haiti_roster = get_real_world_roster("Haiti", "Brazil", "20 Jun 2026")
print("\nHaiti Squad (Starters & Subs):")
for p in haiti_roster:
    sub_desc = f"Sub (in for {p.get('subbed_in_for')} at {p.get('subbed_in_minute')})" if p.get("sub") else "Starter"
    print(f" - #{p.get('jersey')} {p.get('name')} ({p.get('pos')}) - {sub_desc}")
