import json

with open("data/roster_cache.json", "r", encoding="utf-8") as f:
    cache = json.load(f)

bad_keys = []
for k, v in cache.items():
    if k.startswith("matchevents_") and isinstance(v, list):
        for event in v:
            if event.get("minute") == "00" or event.get("minute") == "00'":
                bad_keys.append(k)
                break

print(f"Bad keys found: {bad_keys}")
