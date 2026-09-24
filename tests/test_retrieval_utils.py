from types import SimpleNamespace

from backend.retrieval_utils import (
    BM25Searcher,
    clean_search_query,
    is_live_intent,
    rank_historical_matches,
    reciprocal_rank_fusion,
    team_search_terms,
)


def _doc(text, source="s.txt"):
    return SimpleNamespace(page_content=text, metadata={"source": source})


class TestReciprocalRankFusion:
    def test_each_list_keeps_its_own_ranks(self):
        a, b, c, d = (_doc(t) for t in "abcd")
        # Query 1 found a, b; query 2 found c, d. c is query 2's best hit and must not
        # rank below query 1's second hit just because query 1 was listed first.
        fused = reciprocal_rank_fusion([[(a, 0.9), (b, 0.8)], [(c, 0.9), (d, 0.8)]], top_k=4)
        order = [doc.page_content for doc, _ in fused]
        assert order.index("c") < order.index("b")

    def test_chunks_found_by_several_lists_rank_first(self):
        a, b, c = (_doc(t) for t in "abc")
        fused = reciprocal_rank_fusion([[(a, 1), (b, 1)], [(b, 1), (c, 1)], [(b, 1)]], top_k=3)
        assert fused[0][0].page_content == "b"

    def test_duplicates_within_a_list_count_once(self):
        a, b = _doc("a"), _doc("b")
        fused = reciprocal_rank_fusion([[(a, 1), (_doc("a"), 1), (_doc("a"), 1), (b, 1)]], top_k=2)
        assert [d.page_content for d, _ in fused] == ["a", "b"]
        assert fused[1][1] == 1.0 / (60 + 2)  # b is rank 2, not rank 4


class TestBM25:
    def test_ranks_matching_chunk_first(self):
        docs = [_doc("rodri pivot press resistance"), _doc("klopp gegenpressing counter press"), _doc("inverted fullbacks")]
        results = BM25Searcher(docs).search("Klopp gegenpressing", top_k=2)
        assert results[0][0] is docs[1]
        assert len(results) == 1  # chunks with no matching term aren't returned


class TestLiveIntent:
    def test_history_questions_are_not_live(self):
        assert not is_live_intent("What was the result of the 2014 World Cup final?")
        assert not is_live_intent("How did Argentina win the match against France?")
        assert not is_live_intent("Compare Rodri and Busquets")

    def test_live_questions(self):
        assert is_live_intent("What are today's scores?")
        assert is_live_intent("Latest Arsenal transfer news")
        assert is_live_intent("Who is winning right now in the Premier League?")


class TestHistoricalMatches:
    MATCHES = [
        {"home_team": "Scotland", "away_team": "Iceland", "match_date": "1", "league": "Friendly"},
        {"home_team": "Netherlands", "away_team": "Poland", "match_date": "2", "league": "Friendly"},
        {"home_team": "Arsenal", "away_team": "Brighton", "match_date": "3", "league": "Premier League"},
        {"home_team": "Chelsea", "away_team": "Arsenal", "match_date": "4", "league": "Premier League"},
        {"home_team": "Chelsea", "away_team": "Arsenal", "match_date": "4", "league": "Premier League"},
    ]

    def test_grammar_words_are_not_team_terms(self):
        assert team_search_terms("How did the Arsenal and Chelsea match go?") == ["arsenal", "chelsea"]

    def test_substring_hits_are_dropped_and_head_to_head_ranks_first(self):
        ranked = rank_historical_matches("Arsenal and Chelsea history", self.MATCHES)
        assert [(m["home_team"], m["away_team"]) for m in ranked] == [("Chelsea", "Arsenal"), ("Arsenal", "Brighton")]

    def test_no_team_named_returns_nothing(self):
        assert rank_historical_matches("explain the half spaces", self.MATCHES) == []


class TestCleanSearchQuery:
    def test_keeps_both_teams(self):
        q = clean_search_query("Why did Manchester City dominate the half spaces against Arsenal?")
        assert q == "manchester city dominate half spaces arsenal"

    def test_keeps_hyphenated_terms(self):
        assert "counter-pressing" in clean_search_query("Explain counter-pressing in 2024")
