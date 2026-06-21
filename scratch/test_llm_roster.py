import logging
import json
import sys

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from backend.roster_store import get_real_world_roster

print("Fetching Portugal roster...")
r = get_real_world_roster("Portugal", "Congo DR", "17 Jun 2026")
print("Portugal Roster:")
print(json.dumps(r, indent=2))

print("\nFetching Congo DR roster...")
r_away = get_real_world_roster("Congo DR", "Portugal", "17 Jun 2026")
print("Congo DR Roster:")
print(json.dumps(r_away, indent=2))
