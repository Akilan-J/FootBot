from backend.match_stats import (
    build_espn_match_stats,
    normalize_goal_events,
    parse_api_football_player_stats,
    parse_espn_player_stats,
    reconcile_stats,
    side_of,
)


def _espn_team(name, home_away, **stats):
    labels = {
        "possessionPct": "Possession", "totalShots": "SHOTS", "shotsOnTarget": "ON GOAL",
        "blockedShots": "Blocked Shots", "accuratePasses": "Accurate Passes",
        "totalPasses": "Passes", "wonCorners": "Corner Kicks", "foulsCommitted": "Fouls",
        "yellowCards": "Yellow Cards", "offsides": "Offsides",
    }
    return {
        "team": {"displayName": name},
        "homeAway": home_away,
        "statistics": [
            {"name": k, "label": labels[k], "displayValue": str(v)} for k, v in stats.items()
        ],
    }


class TestSideOf:
    def test_shared_generic_word_is_not_a_match(self):
        assert side_of("Manchester United", "Newcastle United", "Manchester United") == "away"
        assert side_of("Leeds United", "Newcastle United", "Manchester United") is None

    def test_containment_and_accents(self):
        assert side_of("Atlético Madrid", "Atletico Madrid", "Real Madrid") == "home"
        assert side_of("Brazil", "Brazil U20", "Argentina") == "home"


class TestEspnMatchStats:
    def test_reads_shots_on_target_from_the_on_goal_row(self):
        # Blocked Shots is listed first: substring matching on "SHOTS" used to pick it
        home = _espn_team("Arsenal", "home", blockedShots=4, totalShots=15, shotsOnTarget=7,
                          possessionPct=58, accuratePasses=480, totalPasses=550,
                          wonCorners=0, foulsCommitted=9, yellowCards=0, offsides=1)
        away = _espn_team("Chelsea", "away", blockedShots=2, totalShots=8, shotsOnTarget=3,
                          possessionPct=42, accuratePasses=350, totalPasses=420,
                          wonCorners=5, foulsCommitted=12, yellowCards=3, offsides=0)
        stats = build_espn_match_stats({"boxscore": {"teams": [home, away]}}, "Arsenal", "Chelsea")

        assert stats["shots"] == [15, 8]
        assert stats["shotsOnTarget"] == [7, 3]
        # Total passes, not just the completed ones
        assert stats["passes"] == [550, 420]
        assert stats["possession"] == [58, 42]
        # Real zeros stay zeros instead of becoming the old 5/1/2 defaults
        assert stats["corners"] == [0, 5]
        assert stats["yellowCards"] == [0, 3]
        assert stats["offsides"] == [1, 0]

    def test_orders_by_team_name_not_list_position(self):
        away = _espn_team("Chelsea", "away", totalShots=8, shotsOnTarget=3, possessionPct=42)
        home = _espn_team("Arsenal", "home", totalShots=15, shotsOnTarget=7, possessionPct=58)
        stats = build_espn_match_stats({"boxscore": {"teams": [away, home]}}, "Arsenal", "Chelsea")
        assert stats["shots"] == [15, 8]
        assert stats["possession"] == [58, 42]

    def test_no_boxscore_numbers_returns_none(self):
        empty = {"boxscore": {"teams": [_espn_team("A", "home"), _espn_team("B", "away")]}}
        assert build_espn_match_stats(empty, "A", "B") is None


class TestPlayerStats:
    def test_espn_rosters(self):
        summary = {"rosters": [
            {"team": {"displayName": "Argentina"}, "homeAway": "home", "roster": [
                {"athlete": {"displayName": "Lionel Messi"}, "stats": [
                    {"name": "totalGoals", "value": 2}, {"name": "goalAssists", "value": 1},
                    {"name": "totalShots", "value": 5}, {"name": "shotsOnTarget", "value": 3}]},
                {"athlete": {"displayName": "Unused Sub"}, "stats": []},
            ]},
            {"team": {"displayName": "France"}, "homeAway": "away", "roster": [
                {"athlete": {"displayName": "Kylian Mbappé"}, "stats": [
                    {"name": "totalGoals", "value": 3}, {"name": "totalShots", "value": 2}]},
            ]},
        ]}
        rows = {r["name"]: r for r in parse_espn_player_stats(summary, "Argentina", "France")}

        assert rows["Lionel Messi"] == {"name": "Lionel Messi", "team": "Argentina", "goals": 2,
                                        "assists": 1, "shots": 5, "shotsOnTarget": 3}
        # Goals imply shots on target and shots, even if the provider under-reports them
        assert rows["Kylian Mbappé"]["shotsOnTarget"] == 3
        assert rows["Kylian Mbappé"]["shots"] == 3
        assert "Unused Sub" not in rows

    def test_api_football_skips_unused_subs(self):
        payload = {"response": [{"team": {"name": "Arsenal"}, "players": [
            {"player": {"name": "B. Saka"}, "statistics": [
                {"games": {"minutes": 90}, "goals": {"total": 1, "assists": None},
                 "shots": {"total": 4, "on": 2}}]},
            {"player": {"name": "Bench Guy"}, "statistics": [{"games": {"minutes": None}}]},
        ]}]}
        rows = parse_api_football_player_stats(payload, "Arsenal", "Chelsea")
        assert rows == [{"name": "B. Saka", "team": "Arsenal", "goals": 1, "assists": 0,
                         "shots": 4, "shotsOnTarget": 2}]


class TestGoalEvents:
    def test_team_names_are_canonicalised_and_placeholder_assists_dropped(self):
        events = normalize_goal_events(
            [{"minute": "80'", "scorer": "B", "assist": "null", "team": "Chelsea FC"},
             {"minute": "12'", "scorer": "A", "assist": "A", "team": "Arsenal FC"}],
            "Arsenal", "Chelsea",
        )
        assert [e["team"] for e in events] == ["Arsenal", "Chelsea"]  # sorted by minute
        assert all(e["assist"] is None for e in events)

    def test_missed_penalty_is_flagged(self):
        events = normalize_goal_events(
            [{"minute": "30'", "scorer": "A", "team": "Arsenal", "penalty": True, "text": "Missed Penalty"}],
            "Arsenal", "Chelsea",
        )
        assert events[0]["missed"] is True

    def test_own_goal_is_credited_to_the_side_whose_score_it_raised(self):
        # Provider lists the own goal under the scorer's (Chelsea's) team
        events = normalize_goal_events(
            [{"minute": "10'", "scorer": "A", "team": "Arsenal"},
             {"minute": "50'", "scorer": "Chelsea Defender", "team": "Chelsea", "ownGoal": True}],
            "Arsenal", "Chelsea", home_score=2, away_score=0,
        )
        assert [e["team"] for e in events] == ["Arsenal", "Arsenal"]

    def test_own_goal_left_alone_when_already_consistent(self):
        events = normalize_goal_events(
            [{"minute": "50'", "scorer": "Chelsea Defender", "team": "Arsenal", "ownGoal": True}],
            "Arsenal", "Chelsea", home_score=1, away_score=0,
        )
        assert events[0]["team"] == "Arsenal"


class TestReconcileStats:
    def test_shots_never_below_goals_from_shots(self):
        stats = {"shots": [2, 5], "shotsOnTarget": [1, 1]}
        events = [
            {"team": "Arsenal", "scorer": "A"}, {"team": "Arsenal", "scorer": "B"},
            {"team": "Arsenal", "scorer": "C", "penalty": True},
            {"team": "Chelsea", "scorer": "X", "ownGoal": True},
            {"team": "Chelsea", "scorer": "Y", "missed": True},
        ]
        out = reconcile_stats(stats, "Arsenal", "Chelsea", events)
        assert out["shotsOnTarget"] == [3, 1]
        assert out["shots"] == [3, 5]

    def test_falls_back_to_scoreline_and_player_totals(self):
        out = reconcile_stats({"shots": [0, 0], "shotsOnTarget": [0, 0]}, "A", "B",
                              events=[], home_score=1, away_score=0,
                              player_stats=[{"team": "B", "shots": 4, "shotsOnTarget": 2}])
        assert out["shotsOnTarget"] == [1, 2]
        assert out["shots"] == [1, 4]


# ── Play-by-play shots and actions (payload shapes copied from a real ESPN
#    summary: Bournemouth 0-1 Liverpool, 20 Sep 2026) ────────────────────────

from backend.match_stats import parse_espn_player_actions, parse_espn_shots


def _play(pid, type_key, type_text, team, names, minute, text, fx=None, fy=None, gy=None, f2y=None):
    play = {
        "id": pid,
        "type": {"type": type_key, "text": type_text},
        "team": {"displayName": team},
        "participants": [{"athlete": {"displayName": n}} for n in names],
        "clock": {"displayValue": minute},
        "period": {"number": 1},
        "text": text,
    }
    if fx is not None:
        play["fieldPositionX"], play["fieldPositionY"] = fx, fy
    if gy is not None:
        play["goalPositionY"] = gy
    if f2y is not None:
        play["fieldPosition2Y"] = f2y
    return {"text": text, "play": play}


SUMMARY = {"commentary": [
    _play("1", "shot-on-target", "Shot On Target", "AFC Bournemouth", ["Evanilson", "Marcus Tavernier"], "18'",
          "Attempt saved. Evanilson (Bournemouth) left footed shot from the left side of the six yard box is saved "
          "in the bottom left corner by Alisson Becker (Liverpool). Assisted by Marcus Tavernier with a cross.",
          fx=94.3, fy=58.2, gy=54.1),
    _play("2", "shot-off-target", "Shot Off Target", "AFC Bournemouth", ["Ryan Christie", "Alex Scott"], "19'",
          "Attempt missed. Ryan Christie (Bournemouth) header from a difficult angle on the left is too high.",
          fx=95.9, fy=68.2, f2y=52.4),
    _play("3", "shot-blocked", "Shot Blocked", "Liverpool", ["Cody Gakpo", "Florian Wirtz"], "26'",
          "Attempt blocked. Cody Gakpo (Liverpool) right footed shot from outside the box is blocked.",
          fx=81.2, fy=55.0, f2y=53.8),
    _play("4", "goal", "Goal", "Liverpool", ["Alexander Isak"], "57'",
          "Goal! Bournemouth 0, Liverpool 1. Alexander Isak (Liverpool) right footed shot from the centre of the "
          "box to the bottom left corner.", fx=92.3, fy=51.3, gy=52.9),
    _play("5", "penalty---saved", "Penalty - Saved", "Liverpool", ["Mohamed Salah"], "70'",
          "Penalty saved. Mohamed Salah (Liverpool) right footed shot saved in the bottom right corner.",
          fx=88.5, fy=50.0, gy=48.0),
    _play("6", "own-goal", "Own Goal", "AFC Bournemouth", ["James Hill"], "80'",
          "Own Goal by James Hill, Bournemouth.", fx=92.7, fy=50.0),
    _play("7", "foul", "Foul", "AFC Bournemouth", ["Evanilson", "Milos Kerkez"], "4'",
          "Foul by Evanilson (Bournemouth).", fx=70.6, fy=12.7),
    # ESPN writes a foul up once per side - same play id
    _play("7", "foul", "Foul", "AFC Bournemouth", ["Evanilson", "Milos Kerkez"], "4'",
          "Milos Kerkez (Liverpool) wins a free kick in the defensive half.", fx=70.6, fy=12.7),
    _play("8", "offside", "Offside", "AFC Bournemouth", ["Alex Scott"], "30'",
          "Offside, Bournemouth. Ryan Christie is caught offside.", fx=94.8, fy=45.1),
    {"text": "Lineups are announced and players are warming up."},
]}


class TestParseEspnShots:
    def setup_method(self):
        self.shots = {s["id"]: s for s in parse_espn_shots(SUMMARY, "Bournemouth", "Liverpool")}

    def test_every_shot_type_is_classified_and_own_goals_are_not_shots(self):
        assert {k: v["result"] for k, v in self.shots.items()} == {
            "1": "Saved", "2": "Off Target", "3": "Blocked", "4": "Goal", "5": "Saved"}
        assert [k for k, v in self.shots.items() if v["onTarget"]] == ["1", "4", "5"]
        assert self.shots["5"]["penalty"] and not self.shots["4"]["penalty"]

    def test_teams_shooters_and_assisters(self):
        s = self.shots["1"]
        assert (s["team"], s["side"], s["player"], s["assist"]) == ("Bournemouth", "home", "Evanilson", "Marcus Tavernier")
        assert self.shots["4"]["side"] == "away" and self.shots["4"]["assist"] is None

    def test_location_is_in_the_attacking_frame(self):
        # "left side of the six yard box": left of centre (x < 50), right by the goal (small y)
        s = self.shots["1"]
        assert s["x"] == 41.8 and s["y"] == 5.7
        assert self.shots["2"]["x"] < 50  # "from a difficult angle on the left"

    def test_goal_mouth_placement_matches_the_description(self):
        # "bottom left corner" -> left part of the goal, low
        assert 0 < self.shots["1"]["goalMouthX"] < 30 and self.shots["1"]["goalHeight"] == "low"
        assert 0 < self.shots["4"]["goalMouthX"] < 50 and self.shots["4"]["goalHeight"] == "low"
        # "bottom right corner"
        assert self.shots["5"]["goalMouthX"] > 50
        assert self.shots["2"]["goalHeight"] == "over"
        # A blocked shot never reached the goal
        assert self.shots["3"]["goalMouthX"] is None and self.shots["3"]["goalHeight"] is None

    def test_body_part(self):
        assert self.shots["1"]["bodyPart"] == "Left Foot"
        assert self.shots["2"]["bodyPart"] == "Header"
        assert self.shots["4"]["bodyPart"] == "Right Foot"

    def test_penalty_shootout_kicks_are_not_match_shots(self):
        # World Cup final 2022: 3-3 after extra time, then a shootout (period 5)
        summary = {"commentary": [
            _play("1", "goal", "Goal", "Argentina", ["Lionel Messi"], "108'",
                  "Goal! Argentina 3, France 2. Lionel Messi (Argentina) right footed shot from very close range.",
                  fx=97.0, fy=50.0),
            _play("2", "penalty---scored", "Penalty - Scored", "Argentina", ["Paulo Dybala"], "120'",
                  "Goal! Argentina 2(5), France 2(3). Paulo Dybala (Argentina) converts the penalty.",
                  fx=88.5, fy=50.0),
        ]}
        summary["commentary"][1]["play"]["period"] = {"number": 5}
        shots = parse_espn_shots(summary, "Argentina", "France")
        assert [s["player"] for s in shots] == ["Lionel Messi"]
        assert not any(a["player"] == "Paulo Dybala" for a in parse_espn_player_actions(summary, "Argentina", "France"))

    def test_reversed_fixture_keeps_sides_right(self):
        shots = parse_espn_shots(SUMMARY, "Liverpool", "Bournemouth")
        assert {s["player"]: s["side"] for s in shots}["Evanilson"] == "away"


class TestParseEspnPlayerActions:
    def test_fouls_are_deduplicated_and_credited_to_both_players(self):
        acts = parse_espn_player_actions(SUMMARY, "Bournemouth", "Liverpool")
        fouls = [a for a in acts if a["kind"] in ("Foul", "Foul Won")]
        assert len(fouls) == 2
        committed = next(a for a in fouls if a["kind"] == "Foul")
        won = next(a for a in fouls if a["kind"] == "Foul Won")
        assert committed["player"] == "Evanilson" and committed["side"] == "home"
        assert won["player"] == "Milos Kerkez" and won["side"] == "away"
        # Kerkez "wins a free kick in the defensive half": his own half (y > 50),
        # on the left flank where a left back plays (x < 50)
        assert won["y"] > 50 and won["x"] < 50
        assert (committed["x"], committed["y"]) == (round(100 - won["x"], 1), round(100 - won["y"], 1))

    def test_foul_given_in_the_fouled_teams_frame_is_flipped(self):
        # Getafe v Malaga, 20 Sep 2026: this foul's coordinates are in Malaga's
        # frame, which ESPN's own "wins a free kick in the defensive half" betrays.
        summary = {"commentary": [
            _play("9", "foul", "Foul", "Getafe", ["Martín Satriano", "David Larrubia"], "28'",
                  "Foul by Martín Satriano (Getafe).", fx=10.9, fy=18.5),
            _play("9", "foul", "Foul", "Getafe", ["Martín Satriano", "David Larrubia"], "28'",
                  "David Larrubia (Malaga) wins a free kick in the defensive half.", fx=10.9, fy=18.5),
        ]}
        acts = parse_espn_player_actions(summary, "Getafe", "Malaga")
        won = next(a for a in acts if a["kind"] == "Foul Won")
        committed = next(a for a in acts if a["kind"] == "Foul")
        assert won["y"] > 50  # in Larrubia's own half, as the text says
        assert committed["y"] < 50  # Satriano was pressing in Malaga's half

    def test_offsides_are_skipped_and_shots_included(self):
        acts = parse_espn_player_actions(SUMMARY, "Bournemouth", "Liverpool")
        assert not any(a["kind"] == "Offside" for a in acts)
        assert sum(1 for a in acts if a["kind"] == "Shot") == 5


class TestReconcileWithShotEvents:
    def test_listed_shots_raise_lagging_totals(self):
        shots = parse_espn_shots(SUMMARY, "Bournemouth", "Liverpool")
        stats = {"shots": [1, 1], "shotsOnTarget": [0, 0]}
        out = reconcile_stats(stats, "Bournemouth", "Liverpool", shot_events=shots)
        assert out["shots"] == [2, 3]
        assert out["shotsOnTarget"] == [1, 2]


class TestAlignShotOutcomes:
    # Man City 5-3 Sunderland, 20 Sep 2026: officially Malick Fofana had 3 shots, all
    # on target, but the play-by-play lists one of them as "Blocked".
    SHOTS = [
        {"team": "Sunderland", "player": "Malick Fofana", "result": "Blocked", "onTarget": False},
        {"team": "Sunderland", "player": "Malick Fofana", "result": "Saved", "onTarget": True},
        {"team": "Sunderland", "player": "Malick Fofana", "result": "Saved", "onTarget": True},
        {"team": "Sunderland", "player": "Danny Ballard", "result": "Blocked", "onTarget": False},
    ]

    def test_blocked_shot_counted_on_target_when_official_stats_say_so(self):
        from backend.match_stats import align_shot_outcomes
        players = [{"team": "Sunderland", "name": "Malick Fofana", "shots": 3, "shotsOnTarget": 3},
                   {"team": "Sunderland", "name": "Danny Ballard", "shots": 1, "shotsOnTarget": 0}]
        out = align_shot_outcomes(self.SHOTS, players)
        assert sum(1 for s in out if s["onTarget"]) == 3
        assert out[0]["blockedOnTarget"] and out[0]["result"] == "Blocked"
        assert not out[3]["onTarget"]  # Ballard's block stays off target
        assert not self.SHOTS[0]["onTarget"]  # input not mutated

    def test_spelling_differences_between_feeds(self):
        from backend.match_stats import align_shot_outcomes, same_player
        assert same_player("Charalampos Kostoulas", "Charalambos Kostoulas")
        assert same_player("Jérémy Doku", "Jeremy Doku")
        assert not same_player("Brian Brobbey", "Brian Dobbey")
        out = align_shot_outcomes(self.SHOTS, [{"team": "Sunderland", "name": "Malick Fofana ", "shotsOnTarget": 3}])
        assert out[0]["onTarget"]
