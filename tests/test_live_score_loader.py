"""Which scraped BBC competitions the app keeps."""

import pytest

from backend.loaders.live_score_loader import is_tracked_match


@pytest.mark.parametrize("league", [
    "Premier League", "Spanish La Liga", "Italian Serie A", "German Bundesliga", "French Ligue 1",
    "World Cup", "UEFA Nations League", "Concacaf Nations League",
])
def test_tracked_competitions_are_kept(league):
    assert is_tracked_match(league, "Home", "Away")


@pytest.mark.parametrize("league", [
    # Same words, different competitions - substring matching used to let these in
    "Nigerian Premier League", "Ukraine Premier League", "Brazilian Serie A", "Austrian Bundesliga",
    "CAF Africa Cup of Nations Qualifiers", "Major League Soccer",
    "UEFA Women's Nations League",
])
def test_other_competitions_are_dropped(league):
    assert not is_tracked_match(league, "Home", "Away")


def test_womens_sides_are_dropped_even_in_a_tracked_competition():
    assert not is_tracked_match("UEFA Nations League", "England Women", "Spain Women")
