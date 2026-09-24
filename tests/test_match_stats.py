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
        assert stats["passes"] == [480, 350]
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
