import requests

# Let's inspect Iraq vs Norway summary
# Event ID lookup or use a known match. Let's resolve the event first:
from backend.roster_store import _resolve_espn_event

event_id, matched_league, _ = _resolve_espn_event("United States", "Australia", "20260620")
print("Event ID:", event_id)
if event_id:
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{matched_league}/summary?event={event_id}"
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
    if r.status_code == 200:
        data = r.json()
        key_events = data.get("keyEvents", [])
        print(f"Total keyEvents: {len(key_events)}")
        for idx, ev in enumerate(key_events):
            ev_type = ev.get("type", {}).get("text", "")
            if "sub" in ev_type.lower() or "substitution" in ev_type.lower() or "sub" in ev.get("type", {}).get("type", "").lower():
                print(f"\n--- Substitution Event #{idx} ---")
                print("Type:", ev.get("type"))
                print("Clock:", ev.get("clock"))
                print("Text:", ev.get("text"))
                print("ShortText:", ev.get("shortText"))
                print("Team:", ev.get("team"))
                print("Participants:", ev.get("participants"))
