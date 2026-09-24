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
    shot_events: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Makes team shot numbers agree with the goals that were actually scored:
    shots on target can't be fewer than goals from shots, and total shots can't be
    fewer than shots on target (or than the per-player totals, or the shots listed
    in the play-by-play)."""
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

    listed_shots, listed_sot = [0, 0], [0, 0]
    for s in shot_events or []:
        idx = 0 if s.get("side") == "home" else 1 if s.get("side") == "away" else None
        if idx is None:
            continue
        listed_shots[idx] += 1
        listed_sot[idx] += 1 if s.get("onTarget") else 0

    for i in (0, 1):
        stats["shotsOnTarget"][i] = max(stats["shotsOnTarget"][i], goals[i], player_sot[i], listed_sot[i])
        stats["shots"][i] = max(stats["shots"][i], stats["shotsOnTarget"][i], player_shots[i], listed_shots[i])
    return stats


# ── ESPN commentary: shots and on-ball actions ──────────────────────────────
#
# ESPN's play-by-play commentary lists every shot with where it was taken from,
# who took and assisted it, and how it ended. Its per-team shot counts equal the
# boxscore's, so the shotmap can show real shots instead of simulated ones.
#
# ESPN pitch coordinates are relative to the team in `play.team`: fieldPositionX
# runs 0 -> 100 towards the goal that team attacks, fieldPositionY runs 0 -> 100
# from the attacker's right touchline to their left. They are returned in the
# frame the Match Centre draws in - `x` 0 -> 100 from the attacker's left to right,
# `y` 0 at the goal being attacked - so no consumer has to know ESPN's axes.

# Half the goal's width on ESPN's 0-100 pitch-width scale (7.32 m of 68 m)
_GOAL_HALF_WIDTH = 7.32 / 68 * 100 / 2


def _shot_result(type_key: str) -> Optional[str]:
    """Maps an ESPN play type to a shotmap result, or None for a non-shot (own
    goals aren't the scorer's side's shots, so they're excluded too)."""
    t = type_key.lower()
    if "own-goal" in t:
        return None
    if t.startswith("goal") or t == "penalty---scored":
        return "Goal"
    if t in ("shot-on-target", "penalty---saved"):
        return "Saved"
    if t in ("shot-off-target", "penalty---missed"):
        return "Off Target"
    if t == "shot-hit-woodwork":
        return "Woodwork"
    if t == "shot-blocked":
        return "Blocked"
    return None


def _to_view_frame(field_x: Any, field_y: Any) -> Tuple[Optional[float], Optional[float]]:
    fx, fy = _num(field_x), _num(field_y)
    if fx is None or fy is None:
        return None, None
    return round(100 - fy, 1), round(100 - fx, 1)


def _body_part(text: str) -> Optional[str]:
    t = text.lower()
    if "header" in t:
        return "Header"
    if "left footed" in t:
        return "Left Foot"
    if "right footed" in t:
        return "Right Foot"
    return None


def _situation(text: str, type_key: str) -> Optional[str]:
    t = text.lower()
    if "penalty" in type_key:
        return "Penalty"
    if "free kick" in t or "free-kick" in type_key:
        return "Free Kick"
    if "following a corner" in t or "from a corner" in t:
        return "Corner"
    if "fast break" in t:
        return "Fast Break"
    return None


def _goal_height(text: str) -> Optional[str]:
    """How high the shot was, from ESPN's description ("bottom left corner",
    "too high", "high and wide", ...). None when the text doesn't say."""
    t = text.lower()
    if "too high" in t or "high and wide" in t or "over the bar" in t or "over the crossbar" in t:
        return "over"
    if "top " in t or "high centre" in t or "crossbar" in t:
        return "high"
    if "bottom " in t or "low " in t:
        return "low"
    if "centre of the goal" in t:
        return "middle"
    return None


# ESPN numbers a penalty shootout as period 5 (after two halves and two halves of
# extra time). Shootout kicks aren't shots in the match: they're excluded from the
# official shot totals and don't count towards the score.
_SHOOTOUT_PERIOD = 5


def _plays(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Unique match plays (shootout excluded) in match order. ESPN repeats a play
    (a foul is written up once for each side), so plays are de-duplicated by id."""
    seen = set()
    plays = []
    for item in summary.get("commentary", []) or []:
        play = item.get("play")
        if not isinstance(play, dict):
            continue
        if play.get("shootout") or (play.get("period") or {}).get("number") == _SHOOTOUT_PERIOD:
            continue
        pid = play.get("id")
        if pid is not None:
            if pid in seen:
                continue
            seen.add(pid)
        plays.append(play)
    return plays


def _names(play: Dict[str, Any]) -> List[str]:
    out = []
    for p in play.get("participants", []) or []:
        name = (p.get("athlete") or {}).get("displayName")
        if name:
            out.append(name)
    return out


def parse_espn_shots(summary: Dict[str, Any], home: str, away: str) -> List[Dict[str, Any]]:
    """Every shot in an ESPN summary's commentary, with real location and outcome."""
    shots: List[Dict[str, Any]] = []
    for play in _plays(summary):
        type_info = play.get("type", {}) or {}
        type_key = str(type_info.get("type", "") or "")
        result = _shot_result(type_key)
        if result is None:
            continue
        side = side_of((play.get("team") or {}).get("displayName", ""), home, away)
        names = _names(play)
        if side is None or not names:
            continue
        text = str(play.get("text", "") or "")
        x, y = _to_view_frame(play.get("fieldPositionX"), play.get("fieldPositionY"))

        # Where the shot crossed the goal line, as a % of the goal's width from the
        # left post (from the shooter's view). Blocked shots never got there.
        goal_x = None
        if result != "Blocked":
            gy = _num(play.get("goalPositionY"))
            if gy is None:
                gy = _num(play.get("fieldPosition2Y"))
            if gy is not None:
                goal_x = round((50 + _GOAL_HALF_WIDTH - gy) / (2 * _GOAL_HALF_WIDTH) * 100, 1)

        shots.append({
            "id": str(play.get("id") or len(shots)),
            "team": home if side == "home" else away,
            "side": side,
            "player": names[0],
            "assist": names[1] if len(names) > 1 else None,
            "minute": (play.get("clock") or {}).get("displayValue") or "",
            "period": (play.get("period") or {}).get("number"),
            "result": result,
            "isGoal": result == "Goal",
            "onTarget": result in ("Goal", "Saved"),
            "penalty": "penalty" in type_key.lower(),
            "bodyPart": _body_part(text),
            "situation": _situation(text, type_key.lower()),
            "x": x,
            "y": y,
            "goalMouthX": goal_x,
            "goalHeight": _goal_height(text) if result != "Blocked" else None,
            "text": text,
        })
    return shots


# Play types whose coordinates are known to be relative to `play.team` and whose
# first participant is the player who did it. Offsides are left out: ESPN names
# the passer there, not the player caught offside.
_ACTION_TYPES = {"foul": "Foul", "take-on": "Take On", "handball": "Handball"}


_FREE_KICK_WHERE = re.compile(r"wins a free kick (?:in|on) the (defensive half|attacking half|left wing|right wing)")


def _foul_frame_contradicted(texts: List[str], won_x: float, won_y: float) -> bool:
    """True when the "X wins a free kick in the defensive half" line ESPN writes for
    a foul clearly contradicts where the fouled player's point landed. The feed
    occasionally gives a foul's coordinates in the fouled team's frame instead of
    the fouler's; those are flipped. Points within 5% of the halfway line (or the
    middle of the pitch, for wings) are too close to call and left alone."""
    for text in texts:
        m = _FREE_KICK_WHERE.search(text)
        if not m:
            continue
        where = m.group(1)
        if where == "defensive half":
            return won_y < 45
        if where == "attacking half":
            return won_y > 55
        if where == "left wing":
            return won_x > 55
        if where == "right wing":
            return won_x < 45
    return False


def parse_espn_player_actions(summary: Dict[str, Any], home: str, away: str) -> List[Dict[str, Any]]:
    """On-ball actions with a real pitch location, per player: shots, fouls
    committed and won, take-ons and handballs. Each point is in the acting
    player's own frame (`y` 0 = the goal they attack)."""
    texts_by_play: Dict[Any, List[str]] = {}
    for item in summary.get("commentary", []) or []:
        play = item.get("play")
        if isinstance(play, dict) and play.get("id") is not None:
            texts_by_play.setdefault(play["id"], []).append(str(item.get("text") or ""))

    actions: List[Dict[str, Any]] = []
    for play in _plays(summary):
        type_key = str((play.get("type") or {}).get("type", "") or "").lower()
        is_shot = _shot_result(type_key) is not None
        kind = "Shot" if is_shot else _ACTION_TYPES.get(type_key)
        if kind is None:
            continue
        side = side_of((play.get("team") or {}).get("displayName", ""), home, away)
        names = _names(play)
        x, y = _to_view_frame(play.get("fieldPositionX"), play.get("fieldPositionY"))
        if side is None or not names or x is None:
            continue
        minute = (play.get("clock") or {}).get("displayValue") or ""
        team = home if side == "home" else away
        if kind == "Foul" and _foul_frame_contradicted(texts_by_play.get(play.get("id"), []), 100 - x, 100 - y):
            x, y = round(100 - x, 1), round(100 - y, 1)
        actions.append({"player": names[0], "team": team, "side": side, "kind": kind,
                        "x": x, "y": y, "minute": minute})
        if kind == "Foul" and len(names) > 1:
            # The fouled player is on the other side, so the point is mirrored
            other = "away" if side == "home" else "home"
            actions.append({"player": names[1], "team": home if other == "home" else away, "side": other,
                            "kind": "Foul Won", "x": round(100 - x, 1), "y": round(100 - y, 1),
                            "minute": minute})
    return actions


def same_player(a: Any, b: Any) -> bool:
    """The same person under two spellings from one provider ("Charalampos
    Kostoulas" / "Charalambos Kostoulas"): identical once cleaned, or the same
    surname and first initial."""
    ca, cb = _clean(a), _clean(b)
    if not ca or not cb:
        return False
    if ca == cb:
        return True
    ta, tb = ca.split(), cb.split()
    return len(ta) > 1 and len(tb) > 1 and ta[-1] == tb[-1] and ta[0][0] == tb[0][0]


def align_shot_outcomes(
    shots: Optional[List[Dict[str, Any]]],
    player_stats: Optional[List[Dict[str, Any]]],
) -> Optional[List[Dict[str, Any]]]:
    """Makes the play-by-play agree with the official per-player shots on target.

    Official stats count a goal-bound shot blocked by a defender as on target, but
    the play-by-play only calls it "Blocked". When a player's official shots on
    target exceed the saves and goals listed for them, that many of their blocked
    shots are marked on target (keeping the "Blocked" result), so the shotmap and
    the match stats report the same numbers.
    """
    if not shots or not player_stats:
        return shots
    out = [dict(s) for s in shots]
    for p in player_stats:
        mine = [s for s in out if s.get("team") == p.get("team") and same_player(s.get("player"), p.get("name"))]
        missing = int(p.get("shotsOnTarget") or 0) - sum(1 for s in mine if s.get("onTarget"))
        for s in [s for s in mine if s.get("result") == "Blocked"][:max(0, missing)]:
            s["onTarget"] = True
            s["blockedOnTarget"] = True
    return out
