import os
import math
import re
from typing import List, Dict, Any, Tuple, Optional
from collections import Counter
import openai
from duckduckgo_search import DDGS
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

from backend.config import settings
from backend.utils import logger, is_vector_db_ready
from backend.prompts import TACTICAL_ANALYST_SYSTEM_PROMPT, TACTICAL_ANALYST_USER_TEMPLATE

class BM25Searcher:
    """Custom, highly-optimized BM25 Lexical Keyword search engine for document chunks."""
    
    def __init__(self, documents: List[Document]):
        self.documents = documents
        self.doc_count = len(documents)
        self.corpus_size = len(documents)
        
        # Word tokenizer
        self.doc_tokens = [self._tokenize(doc.page_content) for doc in documents]
        self.doc_lens = [len(tokens) for tokens in self.doc_tokens]
        self.avg_doc_len = sum(self.doc_lens) / max(1, self.corpus_size)
        
        # Term frequencies
        self.doc_tfs = [Counter(tokens) for tokens in self.doc_tokens]
        
        # Document frequency for terms
        self.dfs = Counter()
        for tokens in self.doc_tokens:
            self.dfs.update(set(tokens))
            
        # BM25 Hyperparameters
        self.k1 = 1.5
        self.b = 0.75

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\b\w+\b", text.lower())

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Document, float]]:
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
            
        scores = []
        for idx in range(self.doc_count):
            score = 0.0
            doc_tf = self.doc_tfs[idx]
            doc_len = self.doc_lens[idx]
            
            for token in query_tokens:
                tf = doc_tf.get(token, 0)
                df = self.dfs.get(token, 0)
                
                # Standard smoothed IDF
                idf = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1.0)
                
                # BM25 scoring formula
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / max(1.0, self.avg_doc_len)))
                score += idf * (numerator / denominator)
                
            if score > 0.0:
                scores.append((self.documents[idx], score))
                
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

def reciprocal_rank_fusion(
    dense_results: List[Tuple[Document, float]], 
    lexical_results: List[Tuple[Document, float]], 
    top_k: int = 5,
    k: int = 60
) -> List[Tuple[Document, float]]:
    """
    Applies Reciprocal Rank Fusion (RRF) to merge dense FAISS semantic results
    and sparse BM25 lexical results.
    """
    rrf_scores = {}
    
    def get_doc_key(doc: Document) -> str:
        return f"{doc.metadata.get('source', '')}__{doc.page_content[:100]}"
        
    for rank, (doc, score) in enumerate(dense_results):
        key = get_doc_key(doc)
        if key not in rrf_scores:
            rrf_scores[key] = {"doc": doc, "score": 0.0, "dense_score": score, "lexical_score": 0.0}
        rrf_scores[key]["score"] += 1.0 / (k + (rank + 1))
        
    for rank, (doc, score) in enumerate(lexical_results):
        key = get_doc_key(doc)
        if key not in rrf_scores:
            rrf_scores[key] = {"doc": doc, "score": 0.0, "dense_score": 0.0, "lexical_score": score}
        rrf_scores[key]["score"] += 1.0 / (k + (rank + 1))
        
    sorted_keys = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x]["score"], reverse=True)
    
    fused_results = []
    for key in sorted_keys[:top_k]:
        item = rrf_scores[key]
        fused_results.append((item["doc"], item["score"]))
        
    return fused_results

def retrieve_historical_matches_context(query: str) -> str:
    """
    Scans the query for potential team names or keywords, retrieves matches
    from the historical_matches table, and formats them as RAG context.
    """
    try:
        from backend.database import search_historical_matches
    except ImportError:
        return ""
        
    # Extract alphabetic words of length >= 3
    raw_words = re.findall(r"\b[a-zA-Z]+\b", query)
    exclude_words = {
        "versus", "vs", "compare", "analysis", "tactics", "tactical", "formation", "board",
        "play", "player", "players", "coach", "coaches", "manager", "managers", "team", "teams",
        "score", "scores", "result", "results", "match", "matches", "game", "games", "what", "show",
        "tell", "explain", "about", "league", "group", "cup", "world", "final", "semi", "quarter",
        "tiki", "taka", "juego", "posicion", "press", "pressing", "counter", "gegenpress", "gegenpressing",
        "inverted", "fullback", "fullbacks", "pivot", "pivots", "midfielder", "midfielders", "striker",
        "strikers", "winger", "wingers", "defender", "defenders", "goalkeeper", "goalkeepers", "goal",
        "goals", "assist", "assists", "shot", "shots", "pass", "passes", "possession", "defense",
        "fc", "united", "city", "real", "club", "town", "county", "athletic", "some", "more", "detail",
        "details", "information", "info", "history", "recent", "past", "last", "latest", "next",
        "today", "yesterday", "tomorrow", "live", "feed", "news", "report", "reports", "stats",
        "statistics", "scouting", "analyst", "analysis", "tactician", "tactical", "opinion", "opinions"
    }
    
    words = []
    for w in raw_words:
        w_clean = w.strip()
        if w_clean.lower() not in exclude_words and len(w_clean) >= 3:
            words.append(w_clean)
        
    found_matches = []
    seen = set()
    
    for word in words:
        matches = search_historical_matches(word)
        for m in matches:
            match_key = f"{m['home_team']}__{m['away_team']}__{m['match_date']}"
            if match_key not in seen:
                seen.add(match_key)
                found_matches.append(m)
                
    if not found_matches:
        return ""
        
    context_lines = [
        "=== RETRIEVED HISTORICAL MATCH RESULTS (DATABASE) ===",
        "These completed past matches were retrieved from our local SQLite index for grounding:",
        ""
    ]
    
    for idx, m in enumerate(found_matches[:10]):
        home_score = m["home_score"] if m["home_score"] is not None else "?"
        away_score = m["away_score"] if m["away_score"] is not None else "?"
        context_lines.append(
            f"[{idx+1}] Date: {m['match_date']} | League: {m['league']}\n"
            f"    Match Result: {m['home_team']} {home_score} - {away_score} {m['away_team']}"
        )
        context_lines.append("")
        
    logger.info(f"Retrieved {len(found_matches)} historical matches to ground query.")
    return "\n".join(context_lines)


class RAGEngine:
    """Core Retrieval-Augmented Generation Engine for FootBot."""
    
    def __init__(self):
        self.embeddings: Optional[HuggingFaceEmbeddings] = None
        self.vector_store: Optional[FAISS] = None
        self.openai_client: Optional[openai.OpenAI] = None
        self.model_name: str = settings.OPENAI_MODEL_NAME
        self.bm25_searcher: Optional[BM25Searcher] = None
        
        # Load components lazily to prevent long startup locks
        self.initialize_openai()
        self.load_vector_db()

    def initialize_openai(self):
        """Initializes the OpenAI Client if the API key is configured."""
        api_key = settings.OPENAI_API_KEY
        if api_key and not api_key.startswith("your-"):
            try:
                if api_key.startswith("sk-or-"):
                    logger.info("OpenRouter API Key detected. Initializing with OpenRouter base URL...")
                    self.openai_client = openai.OpenAI(
                        api_key=api_key,
                        base_url="https://openrouter.ai/api/v1"
                    )
                    self.model_name = "openai/gpt-4o-mini" if settings.OPENAI_MODEL_NAME == "gpt-4o-mini" else settings.OPENAI_MODEL_NAME
                else:
                    self.openai_client = openai.OpenAI(api_key=api_key)
                    self.model_name = settings.OPENAI_MODEL_NAME
                logger.info(f"OpenAI Client successfully initialized (Model: {self.model_name}).")
            except Exception as e:
                logger.error(f"Error initializing OpenAI Client: {str(e)}")
                self.openai_client = None
                self.model_name = settings.OPENAI_MODEL_NAME
        else:
            logger.warning("OpenAI API Key is missing or default. LLM generation will run in mock mode.")
            self.openai_client = None
            self.model_name = settings.OPENAI_MODEL_NAME

    def load_vector_db(self, force_reload: bool = False) -> bool:
        """
        Loads the persisted FAISS database index.
        Can be called again to reload the database after fresh ingestion.
        """
        if self.vector_store is not None and not force_reload:
            return True
            
        if not is_vector_db_ready():
            logger.warning("FAISS vector database files are missing. Retrieval is disabled.")
            self.vector_store = None
            return False
            
        try:
            logger.info("Loading sentence-transformers embedding model for search...")
            if self.embeddings is None:
                self.embeddings = HuggingFaceEmbeddings(
                    model_name=settings.EMBEDDING_MODEL_NAME,
                    model_kwargs={'device': 'cpu'}
                )
                
            logger.info(f"Loading FAISS index from: {settings.FAISS_DB_PATH}")
            self.vector_store = FAISS.load_local(
                str(settings.FAISS_DB_PATH),
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            logger.info("FAISS vector database successfully loaded.")
            
            # Pre-compile the BM25 searcher index in memory
            try:
                if hasattr(self.vector_store, 'docstore') and hasattr(self.vector_store.docstore, '_dict'):
                    all_docs = list(self.vector_store.docstore._dict.values())
                    if all_docs:
                        self.bm25_searcher = BM25Searcher(all_docs)
                        logger.info(f"Pre-compiled BM25 lexical index with {len(all_docs)} documents.")
                    else:
                        self.bm25_searcher = None
                else:
                    self.bm25_searcher = None
            except Exception as e:
                logger.error(f"Failed to pre-compile BM25 index: {str(e)}")
                self.bm25_searcher = None

            return True
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {str(e)}")
            self.vector_store = None
            self.bm25_searcher = None
            return False

    def retrieve_context(self, query: str, top_k: int) -> List[Tuple[Document, float]]:
        """
        Retrieves the top-k most relevant document chunks based on cosine similarity.
        
        Returns a list of tuples containing the Document and its similarity score.
        """
        if self.vector_store is None:
            # Try loading again (in case it was built since initialization)
            if not self.load_vector_db():
                logger.warning("Retrieval requested but vector store is unavailable.")
                return []
                
        try:
            # similarity_search_with_relevance_scores returns (doc, score)
            results = self.vector_store.similarity_search_with_relevance_scores(query, k=top_k)
            # Filter out results that are negative or extremely low confidence (optional)
            return results
        except Exception as e:
            logger.error(f"Error during similarity search: {str(e)}")
            return []

    def _expand_query(self, query: str) -> List[str]:
        """
        Uses the LLM to generate 3 alternative query formulations for better RAG retrieval.
        Returns a list of queries including the original query.
        """
        if self.openai_client is None:
            return [query]
            
        try:
            prompt = (
                f"You are a helpful assistant that generates alternative search queries for retrieval-augmented generation.\n"
                f"Generate exactly 3 alternative search queries focused on retrieving documents that will help answer the user's tactical question.\n"
                f"Make sure they focus on different aspects, keywords, or synonyms (e.g. 'counter-pressing' vs 'Gegenpress').\n"
                f"Output exactly 3 queries, one per line. Do not number them or add any other text.\n\n"
                f"User Question: {query}"
            )
            
            completion = self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a professional assistant that generates search query formulations. Output only the queries, one per line, without any numbering, bullet points, introduction, or formatting."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=300
            )
            raw = completion.choices[0].message.content
            if raw:
                lines = [line.strip() for line in raw.split("\n") if line.strip()]
                # Strip numbering prefix if LLM didn't follow instructions perfectly
                cleaned_lines = []
                for line in lines:
                    cleaned_line = re.sub(r"^\d+[\.\-\s]+", "", line).strip()
                    cleaned_line = re.sub(r"^[\-\*\s]+", "", cleaned_line).strip()
                    if cleaned_line:
                        cleaned_lines.append(cleaned_line)
                if cleaned_lines:
                    logger.info(f"Expanded query '{query}' into: {cleaned_lines}")
                    return [query] + cleaned_lines[:3]
        except Exception as e:
            logger.error(f"Error during query expansion: {e}")
            
        return [query]

    def _llm_rerank(self, query: str, candidates: List[Document], top_k: int) -> List[Tuple[Document, float]]:
        """
        Scores retrieved document candidate chunks on a scale of 0 to 10 based on their direct relevance
        to the user's tactical query. Returns the top_k candidates sorted by relevance score.
        """
        import json
        if self.openai_client is None or not candidates:
            # Fallback to returning candidates with index-based default scores if LLM client is unavailable
            return [(doc, 1.0 - (idx * 0.05)) for idx, doc in enumerate(candidates[:top_k])]
            
        try:
            logger.info(f"Re-ranking {len(candidates)} document chunks using LLM...")
            
            # Format chunks with identifiers for LLM evaluation
            chunks_text = ""
            for idx, doc in enumerate(candidates):
                content_preview = doc.page_content.replace("\n", " ").strip()
                chunks_text += f"ID: {idx}\nSource: {doc.metadata.get('source', 'Unknown')}\nContent: {content_preview[:800]}\n---\n"
                
            prompt = (
                f"You are an elite football tactical analyst grading retrieved context documents for their relevance to a user query.\n"
                f"User Query: \"{query}\"\n\n"
                f"Evaluate each document chunk below and assign it a relevance score from 0.0 (entirely irrelevant) to 10.0 (highly relevant, directly answers the query or provides critical context).\n"
                f"Respond with a raw JSON object mapping each integer ID to its float score. Example:\n"
                f"{{\n"
                f"  \"0\": 8.5,\n"
                f"  \"1\": 2.0\n"
                f"}}\n"
                f"Output only the raw JSON object. Do not include any reasoning, markdown formatting, or HTML tags.\n\n"
                f"Retrieve chunks to evaluate:\n"
                f"{chunks_text}"
            )
            
            completion = self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a professional grader returning raw JSON scoring objects only. Do not wrap in markdown blocks."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            raw_content = completion.choices[0].message.content
            if raw_content:
                cleaned = raw_content.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
                
                try:
                    scores_dict = json.loads(cleaned)
                except Exception as json_e:
                    logger.warning(f"Standard JSON parsing failed, falling back to regex extraction: {json_e}")
                    scores_dict = {}
                    # Find all "key": value pairs
                    pairs = re.findall(r'["\']?(\d+)["\']?\s*:\s*(\d+\.?\d*)', cleaned)
                    for k, v in pairs:
                        scores_dict[k] = float(v)
                
                scored_docs = []
                for idx, doc in enumerate(candidates):
                    score = float(scores_dict.get(str(idx), scores_dict.get(idx, 0.0)))
                    scored_docs.append((doc, score))
                    
                scored_docs.sort(key=lambda x: x[1], reverse=True)
                logger.info(f"Re-ranked {len(scored_docs)} chunks. Top score: {scored_docs[0][1] if scored_docs else 0.0}")
                return scored_docs[:top_k]
        except Exception as e:
            logger.error(f"Error during LLM re-ranking: {e}")
            
        # Fallback to index order
        return [(doc, 1.0 - (idx * 0.05)) for idx, doc in enumerate(candidates[:top_k])]

    def _clean_search_query(self, query: str) -> str:
        """Simplifies the search query for search engine compatibility."""
        import re
        q = query.lower()
        
        # Strip punctuation
        q = re.sub(r"[?!.,;:\-\"\']", " ", q)
        
        # Strip common question prefixes
        question_patterns = [
            r"^(what was the score of|what was the|who did|how did|why did|explain the|explain|compare|so what if i want to|tell me about|what is|how to)\s+"
        ]
        for pattern in question_patterns:
            q = re.sub(pattern, "", q)
            
        # Strip common stop words
        stop_words = ["vs", "versus", "the", "a", "an", "of", "and", "in", "to", "for", "with", "on", "at", "by"]
        words = [w for w in q.split() if w and w not in stop_words]
        
        if len(words) > 5:
            # Keep top 5 key terms
            words = words[:5]
            
        cleaned = " ".join(words)
        logger.info(f"Simplified query for Web Search: '{query}' ➔ '{cleaned}'")
        return cleaned

    def web_search_fallback(self, query: str, max_results: int = 3, clean: bool = True) -> List[Dict[str, Any]]:
        """Queries Yahoo Search first for clean real-time snippets, falling back to DuckDuckGo if needed."""
        clean_q = self._clean_search_query(query) if clean else query
        logger.info(f"Triggering live web search for query: '{clean_q}'")
        results = []
        
        # 1. Query Yahoo Search (highly reliable, no Javascript requirements, rich snippets)
        try:
            import requests
            from bs4 import BeautifulSoup
            import urllib.parse
            import time
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            # Generate variations of the query if we hit status 500 / other errors
            queries_to_try = [clean_q]
            if "congo dr" in clean_q.lower():
                queries_to_try.append(clean_q.lower().replace("congo dr", "dr congo"))
                queries_to_try.append(clean_q.lower().replace("congo dr", "congo"))
            elif "dr congo" in clean_q.lower():
                queries_to_try.append(clean_q.lower().replace("dr congo", "congo dr"))
                
            for q_idx, q in enumerate(queries_to_try):
                encoded_query = urllib.parse.quote_plus(q)
                url = f"https://search.yahoo.com/search?q={encoded_query}"
                
                # Retry transient 500 errors
                res = None
                for attempt in range(2):
                    try:
                        res = requests.get(url, headers=headers, timeout=10)
                        if res.status_code == 200:
                            break
                        logger.warning(f"Yahoo Search returned status {res.status_code} for query '{q}'. Attempt {attempt+1} of 2. Retrying in 1.0s...")
                        time.sleep(1.0)
                    except Exception as req_e:
                        logger.warning(f"Yahoo Search request failed for '{q}': {req_e}. Retrying in 1.0s...")
                        time.sleep(1.0)
                        
                if res and res.status_code == 200:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    items = soup.find_all(class_='algo')
                    for item in items[:max_results]:
                        h3 = item.find('h3')
                        snippet_div = item.find('div', class_='compText')
                        a = item.find('a')
                        
                        title = h3.text.strip() if h3 else ""
                        body = snippet_div.text.strip() if snippet_div else ""
                        href = a['href'] if a and a.has_attr('href') else ""
                        
                        if title or body:
                            results.append({
                                "title": title,
                                "body": body,
                                "href": href
                            })
                    if results:
                        logger.info(f"Successfully retrieved {len(results)} results from Yahoo search using query '{q}'.")
                        break
        except Exception as y_err:
            logger.error(f"Yahoo Search failed: {str(y_err)}")

        # 2. Fallback to DuckDuckGo Search if Yahoo returned nothing
        if not results:
            logger.info("Yahoo Search returned no results. Falling back to DuckDuckGo...")
            try:
                with DDGS() as ddgs:
                    ddg_generator = ddgs.text(clean_q, backend="html", max_results=max_results)
                    for r in ddg_generator:
                        results.append({
                            "title": r.get("title", ""),
                            "body": r.get("body", ""),
                            "href": r.get("href", "")
                        })
            except Exception as e:
                logger.error(f"DuckDuckGo search encountered an error: {str(e)}")

        return results

    def generate_tactical_analysis(
        self, 
        query: str, 
        top_k: int = None, 
        temperature: float = None
    ) -> Dict[str, Any]:
        """
        Orchestrates the entire RAG pipeline:
        1. Live Intent Check -> Fetch and Prepend BBC Sport RSS updates if needed
        2. Query -> Semantic Retrieval -> Top-K Context Chunks
        3. Score Threshold Evaluation -> Trigger live web search if needed
        4. Format Context & System/User Prompts
        5. Call OpenAI LLM Completion
        6. Return Structured Response + Source Audits
        """
        top_k = top_k or settings.RETRIEVAL_TOP_K
        temperature = temperature or settings.LLM_TEMPERATURE
        
        # 1. Detect Live Intent (scores, live matches, news, transfers) and Historical Matches intent
        import re
        live_keywords = [r"\blive\b", r"\bscore\b", r"\btoday\b", r"\bplaying\b", r"\bmatches\b", r"\bfixture\b", r"\btransfer\b", r"\brumor\b", r"\bnews\b", r"\bmatch\b", r"\bresult\b"]
        is_live_intent = any(re.search(kw, query.lower()) for kw in live_keywords)
        
        is_live_matches_active = False
        live_context = ""
        if is_live_intent:
            logger.info("Live football match/news intent detected. Fetching RSS live feed...")
            try:
                from backend.loaders.live_score_loader import get_live_scores_context
                live_context = get_live_scores_context()
                is_live_matches_active = True
            except Exception as e:
                logger.error(f"Failed to fetch live scores context in RAG: {str(e)}")
                
        # Query local historical SQLite matches
        historical_context = retrieve_historical_matches_context(query)
        
        # 2. Retrieve Local Context Chunks via Hybrid Search (BM25 + FAISS Vector) with Query Expansion
        logger.info(f"Running Hybrid Search with Query Expansion for query: '{query}'")
        queries = self._expand_query(query)
        
        all_dense_results = []
        all_lexical_results = []
        
        # Lazy compile BM25 searcher if needed
        if self.vector_store and self.bm25_searcher is None:
            try:
                if hasattr(self.vector_store, 'docstore') and hasattr(self.vector_store.docstore, '_dict'):
                    all_docs = list(self.vector_store.docstore._dict.values())
                    if all_docs:
                        self.bm25_searcher = BM25Searcher(all_docs)
                        logger.info(f"Compiled lazy BM25 index with {len(all_docs)} documents.")
            except Exception as e:
                logger.error(f"Error compiling lazy BM25 index: {str(e)}")
                
        for q in queries:
            dense_q = self.retrieve_context(q, top_k * 3)
            all_dense_results.extend(dense_q)
            
            if self.bm25_searcher is not None:
                try:
                    lexical_q = self.bm25_searcher.search(q, top_k * 3)
                    all_lexical_results.extend(lexical_q)
                except Exception as e:
                    logger.error(f"Error searching BM25 index for query '{q}': {str(e)}")
                    
        # Deduplicate dense and lexical lists based on page content to avoid RRF noise
        def deduplicate_results(results):
            seen_content = set()
            deduped = []
            for doc, score in results:
                content_summary = doc.page_content[:150]
                if content_summary not in seen_content:
                    seen_content.add(content_summary)
                    deduped.append((doc, score))
            return deduped

        deduped_dense = deduplicate_results(all_dense_results)
        deduped_lexical = deduplicate_results(all_lexical_results)

        # Merge candidates using RRF (ranking candidates over all expanded query formulations)
        fused_candidates = reciprocal_rank_fusion(deduped_dense, deduped_lexical, top_k=top_k * 3)
        candidate_docs = [doc for doc, score in fused_candidates]
        
        # 3. LLM-Based Re-ranking to extract the top-k highest-quality chunks
        retrieved_results = self._llm_rerank(query, candidate_docs, top_k)
        
        logger.info(f"Query Expansion & Hybrid Search retrieved {len(candidate_docs)} candidates; LLM Re-ranking selected top-{len(retrieved_results)} chunks.")
        
        # Evaluate local matching quality (relying on dense vector score of the original query)
        is_local_rag_sufficient = False
        original_dense = self.retrieve_context(query, 1)
        if original_dense:
            max_dense_score = original_dense[0][1]
            if max_dense_score >= settings.RAG_SIMILARITY_THRESHOLD:
                is_local_rag_sufficient = True
                
        # 3. Trigger web search fallback if local data is insufficient
        is_web_search_active = False
        web_results = []
        if settings.WEB_SEARCH_ENABLED and not is_local_rag_sufficient and not is_live_matches_active:
            logger.info(f"Local RAG dense matches insufficient (max dense score: {original_dense[0][1] if original_dense else 0.0:.3f} < threshold: {settings.RAG_SIMILARITY_THRESHOLD}). Executing live search.")
            web_results = self.web_search_fallback(query, max_results=3)
            if web_results:
                is_web_search_active = True
                
        # 4. Format Context and Source Audits
        formatted_context_list = []
        sources = []
        is_rag_active = len(retrieved_results) > 0 or is_web_search_active or is_live_matches_active
        
        if not is_web_search_active:
            # Format Local Chunks only
            for idx, (doc, score) in enumerate(retrieved_results):
                source_name = doc.metadata.get("source", "Unknown")
                page_num = doc.metadata.get("page", None)
                doc_type = doc.metadata.get("type", "unknown")
                
                source_str = f"[{idx+1}] File: {source_name}"
                if page_num:
                    source_str += f", Page: {page_num}"
                source_str += f" (Type: {doc_type}, Relevance Score: {score:.3f})"
                
                formatted_chunk = f"--- Local Context Chunk {idx+1} ({source_str}) ---\n{doc.page_content}\n"
                formatted_context_list.append(formatted_chunk)
                
                sources.append({
                    "index": idx + 1,
                    "text": doc.page_content,
                    "source": source_name,
                    "page": page_num,
                    "type": doc_type,
                    "score": float(score)
                })
        else:
            # Format Web Search Chunks first
            for idx, r in enumerate(web_results):
                source_str = f"[Web {idx+1}] Source: {r['href']} (Title: {r['title']})"
                formatted_chunk = f"--- Real-Time Web Search Result {idx+1} ({source_str}) ---\n{r['body']}\n"
                formatted_context_list.append(formatted_chunk)
                
                sources.append({
                    "index": idx + 1,
                    "text": f"Title: {r['title']}\nSnippet: {r['body']}",
                    "source": r['href'],
                    "page": None,
                    "type": "web_search",
                    "score": 1.0 - (idx * 0.1) # rank-based score
                })
                
            # Append local chunks as supplemental references if they exist
            for idx, (doc, score) in enumerate(retrieved_results):
                local_idx = len(web_results) + idx + 1
                source_name = doc.metadata.get("source", "Unknown")
                page_num = doc.metadata.get("page", None)
                doc_type = doc.metadata.get("type", "unknown")
                
                source_str = f"[{local_idx}] File: {source_name}"
                if page_num:
                    source_str += f", Page: {page_num}"
                source_str += f" (Type: {doc_type}, Relevance Score: {score:.3f})"
                
                formatted_chunk = f"--- Supplementary Local Context Chunk {local_idx} ({source_str}) ---\n{doc.page_content}\n"
                formatted_context_list.append(formatted_chunk)
                
                sources.append({
                    "index": local_idx,
                    "text": doc.page_content,
                    "source": source_name,
                    "page": page_num,
                    "type": doc_type,
                    "score": float(score)
                })
                
        context_block = "\n".join(formatted_context_list) if (len(retrieved_results) > 0 or is_web_search_active) else "NO LOCAL OR WEB CONTEXT RETRIEVED"
        
        # Prepend historical matches context if active
        if historical_context:
            context_block = f"{historical_context}\n\n{context_block}"
            
        # Prepend RSS Live Matches Context if active
        if is_live_matches_active:
            context_block = f"{live_context}\n\n{context_block}"

            
        # 5. Compile Prompts
        system_prompt = TACTICAL_ANALYST_SYSTEM_PROMPT
        user_prompt = TACTICAL_ANALYST_USER_TEMPLATE.format(context=context_block, query=query)
        
        # 6. Generate response via OpenAI (or fallback to Mock)
        response_text = ""
        is_mock = False
        
        if self.openai_client is None:
            self.initialize_openai()
            
        if self.openai_client is not None:
            try:
                completion = self.openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=temperature,
                    max_tokens=4000
                )
                raw_content = completion.choices[0].message.content
                if raw_content:
                    response_text = raw_content
                else:
                    reasoning = getattr(completion.choices[0].message, 'reasoning', None)
                    if reasoning:
                        response_text = f"💡 *Reasoning / Thoughts:*\n{reasoning}\n\n⚠️ *Note: The model's final response was truncated or not generated.*"
                    else:
                        response_text = "⚠️ *The AI model returned an empty response.*"
            except Exception as e:
                logger.error(f"OpenAI API call failed: {str(e)}")
                response_text = f"⚠️ **OpenAI API Execution Error**: {str(e)}\n\n*Please check your internet connection, API billing limits, or API key configurations in the `.env` file.*"
        else:
            is_mock = True
            response_text = self._generate_mock_tactical_response(query, is_rag_active, is_web_search_active, is_live_matches_active, sources)
            
        # Append disclaimer note if not grounded in RAG
        if not is_rag_active:
            disclaimer = "\n\n---\n> 🔍 **RAG Grounding Note**: No specific matches were found in the local FAISS database for this query. This analysis is generated using FootBot's general football tactical models. To anchor this response in custom literature, please ensure your PDFs/blogs are saved in `data/raw` and you have run the re-indexing pipeline."
            response_text += disclaimer
            
        return {
            "query": query,
            "response": response_text,
            "is_rag_active": is_rag_active,
            "is_web_search_active": is_web_search_active,
            "is_live_matches_active": is_live_matches_active,
            "is_mock": is_mock,
            "sources": sources
        }

    def _generate_mock_tactical_response(
        self, 
        query: str, 
        is_rag_active: bool, 
        is_web_search_active: bool,
        is_live_matches_active: bool,
        sources: List[Dict[str, Any]]
    ) -> str:
        """Generates a high-quality, pre-canned tactical mockup response when OpenAI API is not configured."""
        q_lower = query.lower()
        
        intro = "📢 **Demo Mode Active** (OpenAI API Key not configured. Showing high-fidelity simulated response):\n\n"
        
        if is_live_matches_active:
            try:
                from backend.loaders.live_score_loader import fetch_live_football_feed
                feed = fetch_live_football_feed()
                matches = [f for f in feed if f.get("is_match")]
                
                # Check if the query specifically mentions any of the active team names
                target_match = None
                for m in matches:
                    title_lower = m["title"].lower()
                    # Clean the title to isolate team names
                    import re
                    # Remove score digits if present (e.g., "Notts County 3 - 0 Salford City" -> "Notts County   Salford City")
                    title_clean = re.sub(r"\d+", "", title_lower)
                    
                    # Split by common team separators
                    teams = []
                    if " - " in m["title"]:
                        teams = [t.strip() for t in title_clean.split("-") if t.strip()]
                    elif " vs " in title_lower:
                        teams = [t.strip() for t in title_clean.split("vs") if t.strip()]
                    else:
                        # Fallback: split by space and look for key nouns
                        teams = [t.strip() for t in title_clean.split() if len(t.strip()) > 3]
                        
                    # If any of the team names are mentioned in the query
                    if any(t in q_lower for t in teams if len(t) > 3):
                        target_match = m
                        break
                        
                if target_match:
                    title = target_match["title"]
                    desc = target_match["description"]
                    league = target_match.get("league", "Unknown League")
                    
                    return intro + f"""### 📊 Real-Time Tactical Match Analysis: {title}
                    
**🏆 Competition**: {league}  
**⏱️ Match State**: {desc}  

We have compiled the real-time tactical telemetry coordinates for **{title}** currently in progress. Here is our live analyst report:

#### 1. Attacking Shape & Juego de Posición (JdP)
* **Spatial Domination**: In-possession build-up is transitioning from the defensive line using a fluid **3-2-4-1 resting shape**. The double pivot is actively drawing pressers to create vertical passing lanes.
* **Line-Breaking Channels**: Attacking runners are occupying the half-spaces, pulling opponent fullbacks out of their compact structures and creating 1v1 isolation opportunities for touchline-pinned wingers.

#### 2. Rest-Defense Compactness & Pressing Triggers
* **Mid-Block Compress**: Out-of-possession transition establishes an immediate compact mid-block. Strikers are curving their press angles to force distribution wide into designed touchline traps.
* **Counter-Press Swarm**: High counter-pressing triggers are active. Upon transition loss, a compact central bottleneck chokes recovery avenues within 5 seconds to initiate immediate ball recovery.

#### 3. Live Tactical Verdict
Under this match state (**{desc}**), rest-defense security will decide the final points. The chasing side must elevate center-back line height to squeeze half-space pockets, whereas the winning side should utilize *La Pausa* via interior pivots to control tempo.
"""
                
                # General matches feed summary fallback
                if feed:
                    feed_items = "\n".join([f"- **{f['title']}** ({f.get('league', 'Unknown League')}): {f['description']} [Link]({f['link']})" for f in feed[:5]])
                else:
                    feed_items = "- *No live match details or news headlines currently available.*"
            except Exception as e:
                feed_items = f"- *Failed to crawl live feed: {str(e)}*"
                
            return intro + f"""### ⚽ Live Football Scores & Breaking News Feed

Here are today's real-time match details and news headlines retrieved directly from our live HTML scrapers:

{feed_items}

**📊 Tactical Verdict:**
FootBot successfully fetched and processed this live match/news context. To ask our elite tactical analyst agent specific questions about this live feed (e.g. comparing team structures or match statistics), configure your `OPENAI_API_KEY` inside `.env`.
"""

        if is_web_search_active and sources:
            web_sources_str = "\n".join([f"- **Source [{s['index']}]**: {s['source']}\n  *{s['text'].split('Snippet:')[0].replace('Title: ', '')}*" for s in sources if s['type'] == 'web_search'])
            snippets_str = " ".join([s['text'].split('Snippet: ')[1] for s in sources if s['type'] == 'web_search' and 'Snippet: ' in s['text']])
            
            return intro + f"""### 🌐 Live Web Search Tactical Report

We executed a real-time web search to supplement this query due to low local FAISS similarity scores. Here are the retrieved live results:
{web_sources_str}

**⚙️ Synthesized Live Tactical Analysis:**
Based on the latest news and web summaries: *"{snippets_str[:500]}..."*

This dynamic match detail has been parsed to synthesize this layout. To enable complete LLM generative analysis on these snippets, please configure your `OPENAI_API_KEY` inside `.env`.
"""

        if "rodri" in q_lower or "busquets" in q_lower:
            return intro + """### ⚽ Tactical Breakdown: Sergio Busquets vs. Rodri

**1. Positional Discipline and Spatial Awareness**
Sergio Busquets operated primarily as a stationary anchor. His genius was spatial anticipation—often scanning 3 times per second before receiving the ball. His classic *La Pausa* allowed him to freeze pressers and split lines.
Rodri, by contrast, is a dynamic powerhouse in Pep Guardiola’s modern 3-2-4-1. He covers massive distances vertically and laterally, performing robust defensive sweepings while acting as an aggressive second-phase progression threat.

**2. Press Resistance**
- **Sergio Busquets**: Relies on micro-turns, shoulder drops, and instant wall-passes. He redirects pressure rather than fighting it.
- **Rodri**: Relies on physical shielding, powerful recovery strides, and sweeps long diagonals to wingers (averaging high line-breaking volumes).

**🛡️ Tactical Verdict:**
Busquets was the master of *controlling tempo through positioning*; Rodri is the master of *dominating phases through dynamic athleticism and distribution volume*.
"""
        elif "guardiola" in q_lower or "inverted" in q_lower or "positional" in q_lower:
            return intro + """### Pep Guardiola's Inverted Fullback Dynamics

**1. Midfield Box Geometry (3-2-4-1)**
Under Guardiola, inverted fullbacks (e.g., John Stones inverting from center-back) step inside alongside the holding pivot (Rodri). This creates a numerical double-pivot (the "3-2" rest-defense shape) and overloads opponents in central channels.

**2. Half-Space Exploitation**
By pinning defensive lines wide with high touchline wingers, attacking midfielders occupy the half-spaces. When midfielders step up to cover the double-pivot, passing lines open immediately into these half-spaces, generating high-danger vertical progression.

**3. Counter-Press Security**
The 3-2 rest defense setup establishes an instant bottleneck. If possession is lost, five players are positioned compactly in the center to choke counter-attacks instantly.
"""
        elif "gegenpress" in q_lower or "klopp" in q_lower or "press" in q_lower or "arteta" in q_lower:
            return intro + """### Pressing Structures: Gegenpressing vs. Arteta's High Press

**1. Jurgen Klopp's Gegenpress**
The Counter-Press is reactive and ball-oriented. The goal is to trigger intense swarming *immediately* (within 5 seconds) after losing the ball. It is used as a playmaker, exploiting disorganized opponent structures in transition.

**2. Mikel Arteta's High Press**
Highly organized and man-oriented. The press starts from structured blocks with pre-defined "jump triggers." Wingers jump to fullbacks while attacking midfielders step up to mark the holding pivots. Aggressive center-backs (Saliba/Gabriel) squeeze the space vertically.

**⚙️ Key Distinctions:**
- Klopp: Transition-heavy, focused on horizontal narrowing around the ball.
- Arteta: Positional control, focused on strict defensive-block geometries and designated man-marking triggers.
"""
        else:
            # General fallback
            return intro + f"""### ⚽ Football Tactics Analysis: "{query}"

**1. Overview**
Analyzing the query from a spatial geometry standpoint reveals a core modern football conflict. Success hinges on manipulating the opponent's defensive block compactness.

**2. Key Interaction**
- **In-possession**: Teams will look to establish a 3-man build-up line to bypass initial pressure.
- **Out-of-possession**: Strikers will curve their runs to block central passing lanes, forcing the ball wide where touchline traps can be engaged.

**3. Tactical Conclusion**
To address this dilemma, elite coaches construct positional superiority by utilizing interior pivots to draw pressure, creating vertical passing lanes for advanced playmakers in the half-spaces.
"""

# Global instance of RAGEngine
rag_engine = RAGEngine()
