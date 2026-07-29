import requests
import re
import datetime
import threading
import time
import collections
from typing import Dict, Any, List, Optional
from backend.config import settings
from backend.utils import logger
from backend.database import (
    get_api_team_id,
    save_api_team_id,
    get_api_fixture_id,
    save_api_fixture_id
)

# API-Football's free tier caps requests at 10/minute. Enforce a shared, thread-safe
# budget (FastAPI runs sync endpoints in a thread pool, so concurrent requests - e.g.
# rendering many match cards' logos at once - previously fired in an uncoordinated
# burst and instantly tripped the limit, causing most lookups to fail with 429 and
# never resolve). Staying under the cap means every call eventually succeeds and gets
# cached, instead of racing to fail.
_RATE_LOCK = threading.Lock()
_REQUEST_TIMESTAMPS: collections.deque = collections.deque()
_MAX_REQUESTS_PER_MINUTE = 9

def _throttle_api_football_request() -> None:
    while True:
        with _RATE_LOCK:
            now = time.time()
            while _REQUEST_TIMESTAMPS and now - _REQUEST_TIMESTAMPS[0] > 60:
                _REQUEST_TIMESTAMPS.popleft()
            if len(_REQUEST_TIMESTAMPS) < _MAX_REQUESTS_PER_MINUTE:
                _REQUEST_TIMESTAMPS.append(now)
                return
            sleep_for = 60 - (now - _REQUEST_TIMESTAMPS[0]) + 0.1
        time.sleep(max(sleep_for, 0.1))

# Negative-result cache: avoids repeatedly burning rate-limit budget on team names
# that are known not to resolve (e.g. made-up names, or names that failed during a
# prior rate-limited window). Cooldown, not permanent, since a transient failure
# shouldn't block a name forever.
_UNRESOLVED_TEAM_COOLDOWN_SECONDS = 600
_unresolved_teams: Dict[str, float] = {}

# Common shorthand -> the official name API-Football actually indexes the club under.
# Verified against the live API (each maps to the intended club's well-known low team
# ID, e.g. Manchester City=50, Manchester United=33, Tottenham=47, Barcelona=529).
TEAM_NAME_ALIASES: Dict[str, str] = {
    "man city": "Manchester City",
    "man utd": "Manchester United",
    "man united": "Manchester United",
    "spurs": "Tottenham",
    "psg": "Paris Saint Germain",
    "barca": "Barcelona",
}

class APIFootballClient:
    def __init__(self):
        self.api_key = settings.API_FOOTBALL_KEY
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {
            "x-apisports-key": self.api_key
        }

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("API-Football Key is not configured in environment/settings.")
            return None
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            _throttle_api_football_request()
            logger.info(f"API-Football GET request: {url} with params {params}")
            response = requests.get(url, headers=self.headers, params=params, timeout=10.0)
            if response.status_code != 200:
                logger.error(f"API-Football HTTP Error {response.status_code}: {response.text}")
                return None
            data = response.json()
            if data.get("errors"):
                # API-Football returns errors inside errors field in JSON, e.g. request limit exceeded
                logger.error(f"API-Football API Error response: {data['errors']}")
                return None
            return data
        except Exception as e:
            logger.error(f"API-Football Request Exception: {e}")
            return None

    def clean_team_name(self, name: str) -> str:
        """Cleans team name for better search compatibility with API-Football."""
        name = name.strip()
        # Remove common words that interfere with API-Football search
        name = re.sub(r"\b(FC|CF|FK|AC|SC|UD|AFC|RC|Real|Athletic|Club|de|CS|DR|DR Congo|Congo DR)\b", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\s+", " ", name).strip()
        return name

    def resolve_team_id(self, team_name: str) -> Optional[int]:
        """Resolves team name to API-Football team ID using SQLite cache first, then API."""
        team_name_clean = team_name.strip()
        if not team_name_clean:
            return None

        # 0. Common football shorthand doesn't match API-Football's official naming well:
        # e.g. searching "Man City" returns an unrelated Ghanaian club ("Techiman City")
        # rather than Manchester City, because API-Football has no fuzzy alias handling of
        # its own. Normalize known shorthand to the official name it actually indexes under
        # before doing anything else, so the cache key and the query are both canonical.
        canonical = TEAM_NAME_ALIASES.get(team_name_clean.lower())
        if canonical:
            team_name_clean = canonical

        # 1. Check database cache
        cached_id = get_api_team_id(team_name_clean)
        if cached_id is not None:
            logger.info(f"Resolved team '{team_name_clean}' from DB cache: {cached_id}")
            return cached_id

        # 1.5 Skip names that recently failed to resolve, rather than re-spending
        # rate-limit budget on them every time they're requested again.
        cache_key = team_name_clean.lower()
        last_failed_at = _unresolved_teams.get(cache_key)
        if last_failed_at is not None and time.time() - last_failed_at < _UNRESOLVED_TEAM_COOLDOWN_SECONDS:
            return None

        # 2. Try exact name lookup on API-Football
        params = {"name": team_name_clean}
        data = self._get("teams", params=params)
        if data and data.get("response"):
            team_id = data["response"][0]["team"]["id"]
            save_api_team_id(team_name_clean, team_id)
            logger.info(f"Resolved team '{team_name_clean}' via exact API lookup: {team_id}")
            return team_id

        # 3. Clean the name and search API-Football
        search_query = self.clean_team_name(team_name_clean)
        if not search_query:
            search_query = team_name_clean
            
        # Special case for Congo
        if "congo" in team_name_clean.lower():
            search_query = "Congo"

        params = {"search": search_query}
        data = self._get("teams", params=params)
        if data and data.get("response"):
            # Sort/search for the closest matching team name
            best_match = data["response"][0]["team"]
            for item in data["response"]:
                t = item["team"]
                if t["name"].lower() == team_name_clean.lower() or search_query.lower() in t["name"].lower():
                    best_match = t
                    break
            team_id = best_match["id"]
            save_api_team_id(team_name_clean, team_id)
            logger.info(f"Resolved team '{team_name_clean}' via API search '{search_query}': {team_id}")
            return team_id

        logger.warning(f"Could not resolve team ID for '{team_name_clean}'")
        _unresolved_teams[cache_key] = time.time()
        return None

    def resolve_fixture_id(self, home: str, away: str, date_str: str) -> Optional[int]:
        """Resolves match details to API-Football fixture ID using SQLite cache first, then API."""
        home_clean = home.strip()
        away_clean = away.strip()
        
        from backend.roster_store import normalize_date_string
        norm_date = normalize_date_string(date_str)
        if not norm_date:
            logger.error(f"Cannot resolve fixture: invalid or empty date '{date_str}'")
            return None

        # Try to parse normalized date into YYYY-MM-DD
        formatted_date = self._to_yyyy_mm_dd(norm_date)
        if not formatted_date:
            logger.error(f"Cannot convert date '{norm_date}' to YYYY-MM-DD format")
            return None

        # 1. Check database cache
        cached_fixture_id = get_api_fixture_id(home_clean, away_clean, norm_date)
        if cached_fixture_id is not None:
            logger.info(f"Resolved fixture '{home_clean} vs {away_clean}' on '{norm_date}' from DB cache: {cached_fixture_id}")
            return cached_fixture_id

        # 2. Resolve team IDs
        home_id = self.resolve_team_id(home_clean)
        away_id = self.resolve_team_id(away_clean)
        if not home_id or not away_id:
            logger.warning(f"Cannot resolve fixture: missing team ID(s) (home_id: {home_id}, away_id: {away_id})")
            return None

        # 3. Retrieve all fixtures for the date, trying yesterday/tomorrow as well to handle timezone crossings
        dates_to_try = [formatted_date]
        try:
            dt = datetime.datetime.strptime(formatted_date, "%Y-%m-%d")
            yesterday = (dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            tomorrow = (dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            dates_to_try.append(yesterday)
            dates_to_try.append(tomorrow)
        except Exception:
            pass

        for target_date in dates_to_try:
            params = {
                "date": target_date
            }
            data = self._get("fixtures", params=params)

            if data and data.get("response"):
                for item in data["response"]:
                    fixture = item["fixture"]
                    teams = item["teams"]
                    f_home_id = teams["home"]["id"]
                    f_away_id = teams["away"]["id"]
                    # Match both team IDs in either order
                    if (f_home_id == home_id and f_away_id == away_id) or (f_home_id == away_id and f_away_id == home_id):
                        fixture_id = fixture["id"]
                        save_api_fixture_id(home_clean, away_clean, norm_date, fixture_id)
                        logger.info(f"Resolved fixture '{home_clean} vs {away_clean}' on date '{target_date}' via API: {fixture_id}")
                        return fixture_id

        logger.warning(f"Could not resolve fixture ID for '{home_clean} vs {away_clean}' on date range starting from '{formatted_date}'")
        return None

    def fetch_lineup(self, fixture_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves raw lineup data from '/fixtures/lineups' endpoint."""
        return self._get("fixtures/lineups", params={"fixture": fixture_id})

    def fetch_stats(self, fixture_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves raw statistics data from '/fixtures/statistics' endpoint."""
        return self._get("fixtures/statistics", params={"fixture": fixture_id})

    def fetch_events(self, fixture_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves raw events data from '/fixtures/events' endpoint."""
        return self._get("fixtures/events", params={"fixture": fixture_id})

    def map_lineup_to_footbot(self, api_lineups: Dict[str, Any], team_id: int, events_data: Optional[Dict[str, Any]] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Translates raw API-Football lineup data to FootBot-friendly players list with position mappings.
        """
        # Find correct team section in lineups response
        team_section = None
        for section in api_lineups.get("response", []):
            if section.get("team", {}).get("id") == team_id:
                team_section = section
                break
        
        if not team_section:
            logger.warning(f"Lineup section not found for team ID {team_id} in API response.")
            return None

        start_xi_raw = team_section.get("startXI", [])
        substitutes_raw = team_section.get("substitutes", [])
        
        players = []
        outfield_starters = []

        # 1. Parse starting Goalkeeper
        for item in start_xi_raw:
            p_data = item.get("player", {})
            p_pos = p_data.get("pos", "M")
            if p_pos == "G":
                players.append({
                    "name": p_data.get("name", "Unknown"),
                    "jersey": str(p_data.get("number", "1")),
                    "rating": 7.0,
                    "pos": "GK",
                    "photo": "none",
                    "age": "25",
                    "val": "€10M",
                    "height": "185 cm",
                    "sofa_id": str(p_data.get("id", "")),
                    "sub": False,
                    "subbed_in_for": None,
                    "subbed_in_minute": None
                })
            else:
                outfield_starters.append(item)

        # 2. Group outfield starters by their grid row coordinate (X:Y format)
        rows = {}
        for item in outfield_starters:
            p_data = item.get("player", {})
            p_grid = p_data.get("grid") # row:col format
            row_num = 2
            col_num = 1
            if p_grid and ":" in p_grid:
                try:
                    parts = p_grid.split(":")
                    row_num = int(parts[0])
                    col_num = int(parts[1])
                except Exception:
                    pass
            rows.setdefault(row_num, []).append((col_num, item))

        # Classify each row dynamically based on the set of unique row coordinates
        sorted_row_nums = sorted(rows.keys())
        row_categories = {}
        num_rows = len(sorted_row_nums)
        for idx, r_num in enumerate(sorted_row_nums):
            if num_rows == 1:
                row_categories[r_num] = "MID"
            elif num_rows == 2:
                row_categories[r_num] = "DEF" if idx == 0 else "FW"
            elif num_rows == 3:
                row_categories[r_num] = "DEF" if idx == 0 else ("MID" if idx == 1 else "FW")
            elif num_rows == 4:
                row_categories[r_num] = "DEF" if idx == 0 else ("DM" if idx == 1 else ("AM" if idx == 2 else "FW"))
            else:
                if idx == 0:
                    row_categories[r_num] = "DEF"
                elif idx == 1:
                    row_categories[r_num] = "DM"
                elif idx == 2:
                    row_categories[r_num] = "MID"
                elif idx == 3:
                    row_categories[r_num] = "AM"
                else:
                    row_categories[r_num] = "FW"

        # Apply position labels based on sorted column indices (left to right)
        for r_num in sorted_row_nums:
            items_sorted = sorted(rows[r_num], key=lambda x: x[0])
            N = len(items_sorted)
            category = row_categories.get(r_num, "MID")
            
            labels = []
            if category == "DEF":
                if N == 1:
                    labels = ["CB"]
                elif N == 2:
                    labels = ["LCB", "RCB"]
                elif N == 3:
                    labels = ["LCB", "CB", "RCB"]
                elif N == 4:
                    labels = ["LB", "LCB", "RCB", "RB"]
                elif N == 5:
                    labels = ["LWB", "LCB", "CB", "RCB", "RWB"]
                else:
                    labels = ["LB"] + ["CB"]*(N-2) + ["RB"]
            elif category == "DM":
                if N == 1:
                    labels = ["DM"]
                elif N == 2:
                    labels = ["LDM", "RDM"]
                elif N == 3:
                    labels = ["LDM", "DM", "RDM"]
                elif N == 4:
                    labels = ["LM", "LDM", "RDM", "RM"]
                else:
                    labels = ["LM"] + ["DM"]*(N-2) + ["RM"]
            elif category == "MID":
                if N == 1:
                    labels = ["CM"]
                elif N == 2:
                    labels = ["LCM", "RCM"]
                elif N == 3:
                    labels = ["LCM", "CM", "RCM"]
                elif N == 4:
                    labels = ["LM", "LCM", "RCM", "RM"]
                else:
                    labels = ["LM"] + ["CM"]*(N-2) + ["RM"]
            elif category == "AM":
                if N == 1:
                    labels = ["CAM"]
                elif N == 2:
                    labels = ["LAM", "RAM"]
                elif N == 3:
                    labels = ["LW", "CAM", "RW"]
                elif N == 4:
                    labels = ["LW", "LAM", "RAM", "RW"]
                else:
                    labels = ["LW"] + ["CAM"]*(N-2) + ["RW"]
            else: # category == "FW"
                if N == 1:
                    labels = ["ST"]
                elif N == 2:
                    labels = ["LST", "RST"]
                elif N == 3:
                    labels = ["LW", "ST", "RW"]
                elif N == 4:
                    labels = ["LW", "LST", "RST", "RW"]
                else:
                    labels = ["LW"] + ["ST"]*(N-2) + ["RW"]

            for idx, (_, item) in enumerate(items_sorted):
                p_data = item.get("player", {})
                label = labels[idx] if idx < len(labels) else "CM"
                players.append({
                    "name": p_data.get("name", "Unknown"),
                    "jersey": str(p_data.get("number", "")),
                    "rating": 7.0,
                    "pos": label,
                    "photo": "none",
                    "age": "25",
                    "val": "€10M",
                    "height": "180 cm",
                    "sofa_id": str(p_data.get("id", "")),
                    "sub": False,
                    "subbed_in_for": None,
                    "subbed_in_minute": None
                })

        # 3. Parse substitution events to map bench players to their details
        substitutions = []
        if events_data and events_data.get("response"):
            for ev in events_data["response"]:
                if ev.get("type") == "subst" and ev.get("team", {}).get("id") == team_id:
                    sub_in_name = ev.get("player", {}).get("name", "")
                    sub_out_name = ev.get("assist", {}).get("name", "")
                    minute = ev.get("time", {}).get("elapsed", 0)
                    substitutions.append({
                        "in": sub_in_name,
                        "out": sub_out_name,
                        "minute": minute
                    })

        # 4. Parse bench players
        for item in substitutes_raw:
            p_data = item.get("player", {})
            p_pos = p_data.get("pos", "M")
            p_name = p_data.get("name", "")
            
            mapped_pos = "CM"
            if p_pos == "G":
                mapped_pos = "GK"
            elif p_pos == "D":
                mapped_pos = "CB"
            elif p_pos == "M":
                mapped_pos = "CM"
            elif p_pos == "F":
                mapped_pos = "ST"
                
            sub_info = next((s for s in substitutions if s["in"] == p_name or p_name in s["in"] or s["in"] in p_name), None)
            
            players.append({
                "name": p_name,
                "jersey": str(p_data.get("number", "")),
                "rating": 6.0,
                "pos": mapped_pos,
                "photo": "none",
                "age": "25",
                "val": "€10M",
                "height": "180 cm",
                "sofa_id": str(p_data.get("id", "")),
                "sub": True,
                "subbed_in_for": sub_info["out"] if sub_info else None,
                "subbed_in_minute": sub_info["minute"] if sub_info else None
            })
            
        return players

    def _to_yyyy_mm_dd(self, date_str: str) -> Optional[str]:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return date_str
        
        # Try direct strptime parsers
        for fmt in ("%d %b %Y", "%Y-%m-%d", "%d %B %Y"):
            try:
                dt = datetime.datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        
        months = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        match = re.search(r"(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})", date_str)
        if match:
            day = int(match.group(1))
            month_name = match.group(2).lower()
            year = int(match.group(3))
            if month_name in months:
                return datetime.date(year, months[month_name], day).strftime("%Y-%m-%d")
        return None
