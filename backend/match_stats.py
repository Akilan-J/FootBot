"""Pure helpers that turn raw provider payloads (ESPN, API-Football, RAG) into the
match stats, goal events and per-player numbers the Match Centre shows, and keep
them consistent with each other and with the scoreline.

Nothing in here does I/O, so every rule can be unit-tested against canned payloads.
"""

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Tuple

STAT_KEYS = [
    "possession", "shots", "shotsOnTarget", "bigChances", "passes",
    "corners", "fouls", "yellowCards", "offsides",
]

# Words shared by many club names. Matching on these alone paired "Newcastle United"
# with "Manchester United", so they never count as a distinctive overlap.
_GENERIC_TEAM_WORDS = {
    "united", "city", "fc", "cf", "sc", "ac", "afc", "club", "real", "athletic",
    "atletico", "sporting", "town", "rovers", "wanderers", "albion", "county",
    "hotspur", "de", "la", "the", "and", "national", "team", "women",
}


def _clean(text: Any) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text).lower()
    return re.sub(r"\s+", " ", text).strip()


def team_match_score(candidate: str, ours: str) -> int:
    """How well a provider's team name matches ours: 3 exact, 2 one contains the
    other, 1 a distinctive word in common, 0 no match."""
    a, b = _clean(candidate), _clean(ours)
    if not a or not b:
        return 0
    if a == b:
        return 3
    if a in b or b in a:
        return 2
    words_a = {w for w in a.split() if len(w) > 2 and w not in _GENERIC_TEAM_WORDS}
    words_b = {w for w in b.split() if len(w) > 2 and w not in _GENERIC_TEAM_WORDS}
    return 1 if words_a & words_b else 0


def side_of(team: str, home: str, away: str) -> Optional[str]:
    """Returns 'home' or 'away' for a provider team name, or None when it matches
    neither (or both equally well)."""
    h, a = team_match_score(team, home), team_match_score(team, away)
    if h > a:
        return "home"
    if a > h:
        return "away"
    return None


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace("%", "").strip())
    except ValueError:
        return None


# ── ESPN ────────────────────────────────────────────────────────────────────

# ESPN boxscore stats carry a stable `name` and a display `label`. Match the name
# first, then the exact label. Substring label matching picked the wrong row:
# "SHOTS" also hit "Blocked Shots", and "Shots on Goal" never matched ESPN's
# "ON GOAL" label, so shots on target were always estimated as 40% of shots.
_ESPN_TEAM_STATS = {
    "possession": (("possessionPct",), ("possession",)),
    "shots": (("totalShots",), ("shots", "total shots")),
    "shotsOnTarget": (("shotsOnTarget",), ("on goal", "shots on target", "shots on goal")),
    # Total passes, as API-Football reports them - "accuratePasses" is only the completed ones
    "passes": (("totalPasses",), ("passes",)),
    "corners": (("wonCorners",), ("corner kicks", "corners")),
    "fouls": (("foulsCommitted",), ("fouls",)),
    "yellowCards": (("yellowCards",), ("yellow cards",)),
    "offsides": (("offsides",), ("offsides",)),
}


def _espn_stat(stat_list: List[Dict[str, Any]], names: Iterable[str], labels: Iterable[str]) -> Optional[float]:
    by_name = {str(s.get("name", "")).lower(): s for s in stat_list}
    by_label = {str(s.get("label", "")).strip().lower(): s for s in stat_list}
    for key, index in [(n.lower(), by_name) for n in names] + [(l, by_label) for l in labels]:
        s = index.get(key)
        if s is None:
            continue
        val = _num(s.get("value"))
        if val is None:
            val = _num(s.get("displayValue"))
        if val is not None:
            return val
    return None


def parse_espn_team_stats(stat_list: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """Maps one team's ESPN boxscore statistics to our keys (None when absent)."""
    return {key: _espn_stat(stat_list, names, labels) for key, (names, labels) in _ESPN_TEAM_STATS.items()}


def build_espn_match_stats(summary: Dict[str, Any], home: str, away: str) -> Optional[Dict[str, Any]]:
    """Builds home/away match stats from an ESPN summary payload, or None when the
    boxscore has no usable numbers."""
    teams = summary.get("boxscore", {}).get("teams", []) or []
    if len(teams) < 2:
        return None

    home_entry = away_entry = None
    for t in teams:
        name = t.get("team", {}).get("displayName", "")
        side = side_of(name, home, away)
        if side == "home" and home_entry is None:
            home_entry = t
        elif side == "away" and away_entry is None:
            away_entry = t
    if home_entry is None or away_entry is None:
        # Fall back to ESPN's own home/away flag, then list order
        flagged = {t.get("homeAway"): t for t in teams}
        home_entry = flagged.get("home", teams[0])
        away_entry = flagged.get("away", teams[1])

    h = parse_espn_team_stats(home_entry.get("statistics", []) or [])
    a = parse_espn_team_stats(away_entry.get("statistics", []) or [])
    if h["possession"] is None and h["shots"] is None:
        return None

    h_poss, a_poss = h["possession"], a["possession"]
    if h_poss is None and a_poss is None:
        h_poss, a_poss = 50, 50
    elif h_poss is None:
        h_poss = 100 - a_poss
    elif a_poss is None:
        a_poss = 100 - h_poss
    total = h_poss + a_poss
    h_poss = round(h_poss / total * 100) if total > 0 else 50
    a_poss = 100 - h_poss

    def pair(key: str, default: int = 0) -> List[int]:
        # Only a missing stat gets the default: a real 0 (no corners, no cards) stays 0
        return [int(round(h[key])) if h[key] is not None else default,
                int(round(a[key])) if a[key] is not None else default]

    shots = pair("shots")
    sot = [int(round(h["shotsOnTarget"])) if h["shotsOnTarget"] is not None else round(shots[0] * 0.4),
           int(round(a["shotsOnTarget"])) if a["shotsOnTarget"] is not None else round(shots[1] * 0.4)]

    return {
        "possession": [h_poss, a_poss],
        "shots": shots,
        "shotsOnTarget": sot,
        # ESPN has no big-chances stat; shots on target stand in for it
        "bigChances": list(sot),
        "passes": pair("passes"),
        "corners": pair("corners"),
        "fouls": pair("fouls"),
        "yellowCards": pair("yellowCards"),
        "offsides": pair("offsides"),
    }


_ESPN_PLAYER_STATS = {
    "goals": (("totalGoals",), ("G",)),
    "assists": (("goalAssists",), ("A",)),
    "shots": (("totalShots",), ("SH",)),
    "shotsOnTarget": (("shotsOnTarget",), ("ST", "SOG")),
}


def _espn_player_stat(stat_list: List[Dict[str, Any]], names: Iterable[str], abbrevs: Iterable[str]) -> Optional[float]:
    for s in stat_list:
        if s.get("name") in names or s.get("abbreviation") in abbrevs:
            val = _num(s.get("value"))
            if val is None:
                val = _num(s.get("displayValue"))
            if val is not None:
                return val
    return None


def parse_espn_player_stats(summary: Dict[str, Any], home: str, away: str) -> List[Dict[str, Any]]:
    """Per-player goals/assists/shots/shots on target from an ESPN summary's rosters."""
    players: List[Dict[str, Any]] = []
    for team_entry in summary.get("rosters", []) or []:
        side = side_of(team_entry.get("team", {}).get("displayName", ""), home, away)
        if side is None:
            side = team_entry.get("homeAway") if team_entry.get("homeAway") in ("home", "away") else None
        if side is None:
            continue
        for entry in team_entry.get("roster", []) or []:
            name = (entry.get("athlete") or {}).get("displayName")
            stats = entry.get("stats") or []
            if not name or not stats:
                continue
            vals = {k: _espn_player_stat(stats, names, abbrevs) for k, (names, abbrevs) in _ESPN_PLAYER_STATS.items()}
            if all(v is None for v in vals.values()):
                continue
            players.append(_player_row(name, home if side == "home" else away, vals))
    return players


def parse_api_football_player_stats(payload: Dict[str, Any], home: str, away: str) -> List[Dict[str, Any]]:
    """Per-player numbers from API-Football's /fixtures/players response."""
    players: List[Dict[str, Any]] = []
    for team_entry in (payload or {}).get("response", []) or []:
        side = side_of(team_entry.get("team", {}).get("name", ""), home, away)
        if side is None:
            continue
        for entry in team_entry.get("players", []) or []:
            name = (entry.get("player") or {}).get("name")
            stat_blocks = entry.get("statistics") or [{}]
            s = stat_blocks[0] or {}
            if not name:
                continue
            minutes = _num((s.get("games") or {}).get("minutes"))
            if not minutes:
                continue  # unused substitute
            vals = {
                "goals": _num((s.get("goals") or {}).get("total")),
                "assists": _num((s.get("goals") or {}).get("assists")),
                "shots": _num((s.get("shots") or {}).get("total")),
                "shotsOnTarget": _num((s.get("shots") or {}).get("on")),
            }
            players.append(_player_row(name, home if side == "home" else away, vals))
    return players


def _player_row(name: str, team: str, vals: Dict[str, Optional[float]]) -> Dict[str, Any]:
    goals = int(vals.get("goals") or 0)
    sot = int(vals.get("shotsOnTarget") or 0)
    shots = int(vals.get("shots") or 0)
    # A goal is a shot on target, and a shot on target is a shot
    sot = max(sot, goals)
    shots = max(shots, sot)
    return {
        "name": name,
        "team": team,
        "goals": goals,
        "assists": int(vals.get("assists") or 0),
        "shots": shots,
        "shotsOnTarget": sot,
    }


# ── Goal events ─────────────────────────────────────────────────────────────

def _is_missed(event: Dict[str, Any]) -> bool:
    if event.get("missed"):
        return True
    text = " ".join(str(event.get(k) or "") for k in ("text", "detail")).lower()
    return "missed" in text or "saved penalty" in text or "penalty saved" in text


def credited_goals(events: List[Dict[str, Any]], home: str, away: str) -> Tuple[int, int]:
    """Goals per side as they count on the scoreboard (own goals included)."""
    h = a = 0
    for ev in events:
        if _is_missed(ev):
            continue
        side = side_of(ev.get("team", ""), home, away)
        if side == "home":
            h += 1
        elif side == "away":
            a += 1
    return h, a


def normalize_goal_events(
    events: Optional[List[Dict[str, Any]]],
    home: str,
    away: str,
    home_score: Optional[int] = None,
    away_score: Optional[int] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Cleans goal events so every consumer can trust them:

    - `team` is set to exactly `home` or `away` (the side the goal counts for), so
      the UI never has to fuzzy-match team names;
    - missed/saved penalties carry `missed: True` and never count as goals;
    - own goals are credited to the side whose score they raised. Providers differ
      on whether an own goal's team is the scorer's side or the beneficiary, so
      when the tally disagrees with the scoreline and flipping own goals fixes it,
      the own goals are flipped.
    """
    if events is None:
        return None

    cleaned: List[Dict[str, Any]] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        ev = dict(ev)
        assist = ev.get("assist")
        if isinstance(assist, str) and assist.strip().lower() in ("", "null", "none", "unknown", "n/a"):
            assist = None
        if assist and assist == ev.get("scorer"):
            assist = None
        ev["assist"] = assist
        ev["ownGoal"] = bool(ev.get("ownGoal"))
        ev["penalty"] = bool(ev.get("penalty"))
        ev["missed"] = _is_missed(ev)
        side = side_of(ev.get("team", ""), home, away)
        if side:
            ev["team"] = home if side == "home" else away
        cleaned.append(ev)

    if home_score is not None and away_score is not None:
        if credited_goals(cleaned, home, away) != (home_score, away_score):
            flipped = []
            for ev in cleaned:
                if ev["ownGoal"] and not ev["missed"]:
                    side = side_of(ev.get("team", ""), home, away)
                    if side:
                        ev = dict(ev, team=away if side == "home" else home)
                flipped.append(ev)
            if credited_goals(flipped, home, away) == (home_score, away_score):
                cleaned = flipped

    def minute_key(ev: Dict[str, Any]) -> float:
        nums = re.findall(r"\d+", str(ev.get("minute", "")))
        if not nums:
            return 999
        return int(nums[0]) + (int(nums[1]) / 100 if len(nums) > 1 else 0)

    cleaned.sort(key=minute_key)
    return cleaned


def shooter_goals(events: List[Dict[str, Any]], home: str, away: str) -> Tuple[int, int]:
    """Goals per side that came from that side's own shots (own goals excluded)."""
    h = a = 0
    for ev in events:
        if ev.get("missed") or _is_missed(ev) or ev.get("ownGoal"):
            continue
        side = side_of(ev.get("team", ""), home, away)
        if side == "home":
            h += 1
        elif side == "away":
            a += 1
    return h, a


def reconcile_stats(
    stats: Optional[Dict[str, Any]],
    home: str,
    away: str,
    events: Optional[List[Dict[str, Any]]] = None,
    home_score: Optional[int] = None,
    away_score: Optional[int] = None,
    player_stats: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Makes team shot numbers agree with the goals that were actually scored:
    shots on target can't be fewer than goals from shots, and total shots can't be
    fewer than shots on target (or than the per-player totals)."""
    if not stats:
        return stats
    stats = dict(stats)
    for key in ("shots", "shotsOnTarget"):
        val = stats.get(key)
        if not (isinstance(val, list) and len(val) == 2):
            stats[key] = [0, 0]
        else:
            stats[key] = [max(0, int(_num(v) or 0)) for v in val]

    if events:
        goals = list(shooter_goals(events, home, away))
    elif home_score is not None and away_score is not None:
        goals = [home_score, away_score]
    else:
        goals = [0, 0]

    player_shots, player_sot = [0, 0], [0, 0]
    for p in player_stats or []:
        idx = 0 if p.get("team") == home else 1 if p.get("team") == away else None
        if idx is None:
            continue
        player_shots[idx] += int(p.get("shots") or 0)
        player_sot[idx] += int(p.get("shotsOnTarget") or 0)

    for i in (0, 1):
        stats["shotsOnTarget"][i] = max(stats["shotsOnTarget"][i], goals[i], player_sot[i])
        stats["shots"][i] = max(stats["shots"][i], stats["shotsOnTarget"][i], player_shots[i])
    return stats
