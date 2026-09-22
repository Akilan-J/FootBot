"""Historical match storage: dedup rules and retrieval."""


def test_new_match_is_inserted(db):
    db.save_historical_match("Arsenal", "Chelsea", 2, 1, "22 Sep 2024", "Premier League")

    matches = db.get_historical_matches()
    assert len(matches) == 1
    assert matches[0]["home_team"] == "Arsenal"
    assert (matches[0]["home_score"], matches[0]["away_score"]) == (2, 1)


def test_rescraping_same_match_updates_instead_of_duplicating(db):
    db.save_historical_match("Arsenal", "Chelsea", 0, 0, "22 Sep 2024", "Premier League")
    db.save_historical_match("Arsenal", "Chelsea", 2, 1, "22 Sep 2024", "Premier League")

    matches = db.get_historical_matches()
    assert len(matches) == 1
    assert (matches[0]["home_score"], matches[0]["away_score"]) == (2, 1)


def test_match_scraped_with_teams_reversed_is_not_duplicated(db):
    """Regression: BBC can list the same fixture with home/away swapped. Matching only
    the exact home/away order used to insert a second row for the same match."""
    db.save_historical_match("France", "Norway", 0, 0, "27 Jun 2026", "World Cup")
    db.save_historical_match("Norway", "France", 1, 4, "27 Jun 2026", "World Cup")

    matches = db.get_historical_matches()
    assert len(matches) == 1


def test_reversed_match_keeps_scores_aligned_with_stored_teams(db):
    """The flipped payload must not write the home team's goals into the away column."""
    db.save_historical_match("France", "Norway", 0, 0, "27 Jun 2026", "World Cup")
    db.save_historical_match("Norway", "France", 1, 4, "27 Jun 2026", "World Cup")

    match = db.get_historical_matches()[0]
    assert match["home_team"] == "France"
    # Norway 1-4 France means France (the stored home team) scored 4.
    assert (match["home_score"], match["away_score"]) == (4, 1)


def test_same_teams_on_a_different_date_is_a_separate_match(db):
    db.save_historical_match("France", "Norway", 1, 0, "27 Jun 2026", "World Cup")
    db.save_historical_match("France", "Norway", 2, 2, "15 Oct 2026", "World Cup")

    assert len(db.get_historical_matches()) == 2


def test_team_name_matching_is_case_insensitive(db):
    db.save_historical_match("Arsenal", "Chelsea", 1, 0, "22 Sep 2024", "Premier League")
    db.save_historical_match("ARSENAL", "chelsea", 3, 0, "22 Sep 2024", "Premier League")

    matches = db.get_historical_matches()
    assert len(matches) == 1
    assert (matches[0]["home_score"], matches[0]["away_score"]) == (3, 0)


def test_search_historical_matches_finds_either_side(db):
    db.save_historical_match("Arsenal", "Chelsea", 2, 1, "22 Sep 2024", "Premier League")

    assert len(db.search_historical_matches("Arsenal")) == 1
    assert len(db.search_historical_matches("Chelsea")) == 1
    assert db.search_historical_matches("Liverpool") == []
