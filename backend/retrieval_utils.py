"""Pure retrieval helpers for the RAG pipeline: lexical search, rank fusion, intent
detection and query cleanup. No model or network imports, so they're unit-testable."""

import math
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Sequence, Tuple

# Words that carry no retrieval signal. Used to keep grammar out of the historical
# match lookup (where "and" used to match "Scotland" and "the" "Netherlands") and
# out of simplified web-search queries.
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "of", "in", "on", "at", "to", "for", "from", "by",
    "with", "without", "vs", "versus", "v", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "have", "has", "had", "can", "could", "would", "should", "will", "shall",
    "may", "might", "must", "what", "which", "who", "whom", "whose", "why", "how", "when", "where",
    "this", "that", "these", "those", "it", "its", "his", "her", "their", "they", "them", "he",
    "she", "we", "you", "your", "our", "my", "me", "i", "us", "so", "if", "then", "than", "as",
    "about", "into", "over", "under", "between", "against", "during", "after", "before", "also",
    "just", "only", "very", "more", "most", "some", "any", "all", "each", "such", "not", "no",
    "tell", "explain", "show", "give", "want", "know", "think", "like", "please", "compare",
}

# Football words that appear in many team or league names or questions but don't
# identify a team on their own.
_GENERIC_FOOTBALL_WORDS = {
    "fc", "cf", "sc", "ac", "afc", "united", "city", "real", "club", "town", "county", "athletic",
    "sporting", "rovers", "wanderers", "albion", "hotspur", "national", "team", "teams", "women",
    "league", "cup", "world", "final", "semi", "quarter", "group", "round", "premier", "division",
    "championship", "match", "matches", "game", "games", "score", "scores", "result", "results",
    "goal", "goals", "win", "won", "lose", "lost", "draw", "beat", "play", "played", "playing",
    "player", "players", "coach", "manager", "tactics", "tactical", "formation", "press", "pressing",
    "season", "history", "recent", "last", "latest", "next", "today", "yesterday", "tomorrow", "live",
    "stats", "statistics", "analysis", "news", "report", "home", "away",
}


def tokenize(text: str) -> List[str]:
    return re.findall(r"\b\w+\b", (text or "").lower())


class BM25Searcher:
    """BM25 lexical keyword search over document chunks (anything with `page_content`)."""

    def __init__(self, documents: Sequence[Any]):
        self.documents = list(documents)
        self.doc_count = len(self.documents)
        self.doc_tokens = [tokenize(doc.page_content) for doc in self.documents]
        self.doc_lens = [len(tokens) for tokens in self.doc_tokens]
        self.avg_doc_len = sum(self.doc_lens) / max(1, self.doc_count)
        self.doc_tfs = [Counter(tokens) for tokens in self.doc_tokens]
        self.dfs: Counter = Counter()
        for tokens in self.doc_tokens:
            self.dfs.update(set(tokens))
        self.k1 = 1.5
        self.b = 0.75

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Any, float]]:
        # Unique terms: repeating a word in the question shouldn't double its weight
        query_tokens = list(dict.fromkeys(tokenize(query)))
        if not query_tokens:
            return []
        scores = []
        for idx in range(self.doc_count):
            score = 0.0
            doc_tf = self.doc_tfs[idx]
            norm = 1.0 - self.b + self.b * (self.doc_lens[idx] / max(1.0, self.avg_doc_len))
            for token in query_tokens:
                tf = doc_tf.get(token, 0)
                if not tf:
                    continue
                df = self.dfs.get(token, 0)
                idf = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1.0)
                score += idf * (tf * (self.k1 + 1.0)) / (tf + self.k1 * norm)
            if score > 0.0:
                scores.append((self.documents[idx], score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


def doc_key(doc: Any) -> str:
    return f"{doc.metadata.get('source', '')}__{doc.page_content}"


def reciprocal_rank_fusion(
    ranked_lists: Iterable[Sequence[Tuple[Any, float]]],
    top_k: int = 5,
    k: int = 60,
) -> List[Tuple[Any, float]]:
    """Merges several independently ranked result lists (e.g. dense and BM25 results
    for each expanded query) with Reciprocal Rank Fusion. Each list keeps its own
    ranks, so no query's results outrank another's just by being listed first, and
    a chunk found by several lists accumulates score. Duplicate chunks within one
    list only count once."""
    fused: Dict[str, Dict[str, Any]] = {}
    for results in ranked_lists:
        seen_in_list = set()
        rank = 0
        for doc, _score in results:
            key = doc_key(doc)
            if key in seen_in_list:
                continue
            seen_in_list.add(key)
            rank += 1
            entry = fused.setdefault(key, {"doc": doc, "score": 0.0})
            entry["score"] += 1.0 / (k + rank)
    ordered = sorted(fused.values(), key=lambda e: e["score"], reverse=True)
    return [(e["doc"], e["score"]) for e in ordered[:top_k]]


# Questions about what is happening now. Words like "match", "score" or "result"
# alone are not enough: "the result of the 2014 final" is a history question.
_LIVE_PATTERNS = [
    r"\blive\b", r"\btoday'?s?\b", r"\btonight'?s?\b", r"\bright now\b", r"\bcurrently\b",
    r"\bat the moment\b", r"\blatest\b", r"\bthis (?:week|weekend)'?s?\b", r"\bfixtures?\b",
    r"\bupcoming\b", r"\btransfers?\b", r"\brumou?rs?\b", r"\bnews\b", r"\bheadlines?\b",
    r"\bin[- ]play\b", r"\bongoing\b", r"\bwho is winning\b", r"\bwhat'?s the score\b",
]


def is_live_intent(query: str) -> bool:
    q = (query or "").lower()
    return any(re.search(p, q) for p in _LIVE_PATTERNS)


def team_search_terms(query: str) -> List[str]:
    """Words from a query that could be (part of) a team name."""
    terms = []
    for w in re.findall(r"[^\W\d_]+", query or ""):
        wl = w.lower()
        if len(wl) >= 3 and wl not in STOP_WORDS and wl not in _GENERIC_FOOTBALL_WORDS and wl not in terms:
            terms.append(wl)
    return terms


def rank_historical_matches(query: str, candidates: Iterable[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    """Keeps matches where a query term is a whole word of a team name (not a
    substring), ranking head-to-heads between two mentioned teams first."""
    terms = set(team_search_terms(query))
    if not terms:
        return []
    ranked = []
    seen = set()
    for m in candidates:
        key = (m.get("home_team"), m.get("away_team"), m.get("match_date"))
        if key in seen:
            continue
        seen.add(key)
        home_hit = bool(terms & set(tokenize(m.get("home_team", ""))))
        away_hit = bool(terms & set(tokenize(m.get("away_team", ""))))
        if home_hit or away_hit:
            ranked.append((2 if home_hit and away_hit else 1, m))
    ranked.sort(key=lambda x: x[0], reverse=True)  # stable: keeps recency order within a tier
    return [m for _, m in ranked[:limit]]


_QUESTION_PREFIX = re.compile(
    r"^(what was the score of|what was the|who did|how did|why did|explain the|explain|compare|"
    r"so what if i want to|tell me about|what is|what are|how to|how does|why does)\s+"
)


def clean_search_query(query: str, max_terms: int = 8) -> str:
    """Turns a chat question into a compact web-search query."""
    q = (query or "").lower()
    q = re.sub(r"[?!.,;:\"]", " ", q)
    q = re.sub(r"\s+-\s+|\s+-|-\s+", " ", q)  # stray dashes, keeping hyphenated words
    q = _QUESTION_PREFIX.sub("", q.strip())
    words = [w.strip("'") for w in q.split()]
    words = [w for w in words if w and w not in STOP_WORDS]
    return " ".join(words[:max_terms])
