#!/usr/bin/env python3
"""Diagnostic script to trace ESPN events lookup for today's live matches."""
import sys
sys.path.insert(0, '.')
import datetime
import requests

today = datetime.date.today().strftime("%Y%m%d")
print(f"Today (ESPN format): {today}")

ESPN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

LEAGUES = [
    "fifa.world", "uefa.champions", "uefa.europa",
    "eng.1", "esp.1", "ger.1", "ita.1", "fra.1",
    "usa.1", "concacaf.nations.league", "conmebol.copa", "afc.asian.cup",
    "caf.cn", "caf.nations", "fifa.confederations",
    "fifa.worldq.caf", "global",
]

home = "Portugal"
away = "Congo DR"

for slug in LEAGUES:
    try:
        r = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={today}",
            headers=ESPN_HEADERS,
            timeout=6,
        )
        events = r.json().get("events", []) if r.status_code == 200 else []
        if events:
            for ev in events:
                for comp in ev.get("competitions", []):
                    names = [c.get("team", {}).get("displayName", "") for c in comp.get("competitors", [])]
                    status = ev.get("status", {}).get("type", {}).get("description", "?")
                    print(f"  [{slug}] {names} — {status}")
                    if any(home.lower() in n.lower() or n.lower() in home.lower() for n in names):
                        event_id = comp.get("id")
                        print(f"    *** MATCH FOUND! event_id={event_id} slug={slug} ***")
                        # Try summary
                        sum_r = requests.get(
                            f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/summary?event={event_id}",
                            headers=ESPN_HEADERS, timeout=8
                        )
                        if sum_r.status_code == 200:
                            key_events = sum_r.json().get("keyEvents", [])
                            scoring_plays = [e for e in key_events if e.get("scoringPlay")]
                            print(f"    keyEvents total: {len(key_events)}, scoringPlays: {len(scoring_plays)}")
                            for sp in scoring_plays:
                                print(f"      -> {sp.get('shortText','?')} @{sp.get('clock',{}).get('displayValue','?')} team={sp.get('team',{}).get('displayName','?')}")
                        else:
                            print(f"    summary fetch failed: {sum_r.status_code}")
        else:
            print(f"  [{slug}] no events (status={r.status_code})")
    except Exception as e:
        print(f"  [{slug}] error: {e}")
