import math
import os
import re
import time
from typing import List, Dict, Any, Tuple, Optional
import openai
from ddgs import DDGS
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

from backend.config import settings
from backend.utils import logger, is_vector_db_ready
from backend.prompts import TACTICAL_ANALYST_SYSTEM_PROMPT, TACTICAL_ANALYST_USER_TEMPLATE

# Re-exported here so existing `from backend.rag_engine import BM25Searcher` keeps working
from backend.retrieval_utils import (  # noqa: E402
    BM25Searcher,
    clean_search_query,
    is_live_intent,
    rank_historical_matches,
    reciprocal_rank_fusion,
    team_search_terms,
)

# Reranker scores are 0-10. Chunks the LLM grades below this are dropped rather
# than passed to the answer as "grounding".
RERANK_MIN_SCORE = 3.0

# How much of the conversation is replayed to the LLM for follow-up questions.
HISTORY_MAX_TURNS = 6
HISTORY_MAX_CHARS_PER_TURN = 1500


def retrieve_historical_matches_context(query: str) -> str:
    """
    Finds teams named in the query, retrieves their matches from the
    historical_matches table, and formats them as RAG context.
    """
    try:
        from backend.database import search_historical_matches
    except ImportError:
        return ""

    candidates = []
    for term in team_search_terms(query):
        candidates.extend(search_historical_matches(term))
    found_matches = rank_historical_matches(query, candidates, limit=10)
    if not found_matches:
        return ""

    context_lines = [
        "=== RETRIEVED HISTORICAL MATCH RESULTS (DATABASE) ===",
        "These completed past matches were retrieved from our local SQLite index for grounding:",
        ""
    ]
    for idx, m in enumerate(found_matches):
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
                # The SDK defaults to a 600s read timeout. Roster generation retries up
                # to three times, so one unresponsive completion could tie up a lookup
                # for half an hour. Bound it: generous for a slow free-tier generation,
                # but not open-ended.
                timeout = settings.LLM_REQUEST_TIMEOUT_SECONDS
                if api_key.startswith("sk-or-"):
                    logger.info("OpenRouter API Key detected. Initializing with OpenRouter base URL...")
                    self.openai_client = openai.OpenAI(
                        api_key=api_key,
                        base_url="https://openrouter.ai/api/v1",
                        timeout=timeout
                    )
                    self.model_name = "openai/gpt-4o-mini" if settings.OPENAI_MODEL_NAME == "gpt-4o-mini" else settings.OPENAI_MODEL_NAME
                else:
                    self.openai_client = openai.OpenAI(api_key=api_key, timeout=timeout)
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
            # The index is IndexFlatL2 over unit-length embeddings and returns squared L2
            # distances. This is the same 1 - d/sqrt(2) mapping LangChain's relevance
            # scores use (so RAG_SIMILARITY_THRESHOLD keeps its meaning), clamped to
            # [0, 1]: unclamped, weak matches went negative and LangChain warned on
            # every search.
            results = self.vector_store.similarity_search_with_score(query, k=top_k)
            return [(doc, max(0.0, min(1.0, 1.0 - float(dist) / math.sqrt(2)))) for doc, dist in results]
        except Exception as e:
            logger.error(f"Error during similarity search: {str(e)}")
            return []

    def _condense_query(self, query: str, history: List[Dict[str, str]]) -> str:
        """Rewrites a follow-up ("what about his passing?") into a standalone question
        using the conversation, so retrieval searches for what was actually asked."""
        if self.openai_client is None or not history:
            return query
        transcript = "\n".join(
            f"{turn['role'].upper()}: {turn['content'][:600]}" for turn in history[-4:]
        )
        try:
            completion = self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You rewrite follow-up questions into standalone search questions. Output only the rewritten question."},
                    {"role": "user", "content": (
                        f"Conversation so far:\n{transcript}\n\n"
                        f"Follow-up question: {query}\n\n"
                        "Rewrite the follow-up as a single standalone question that names the players, teams "
                        "or concepts it refers to. If it is already standalone, return it unchanged."
                    )}
                ],
                temperature=0.0,
                max_tokens=120
            )
            rewritten = (completion.choices[0].message.content or "").strip().strip('"')
            if rewritten:
                logger.info(f"Condensed follow-up '{query}' into standalone query '{rewritten}'")
                return rewritten
        except Exception as e:
            logger.error(f"Error condensing follow-up query: {e}")
        return query

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
                relevant = [(doc, score) for doc, score in scored_docs if score >= RERANK_MIN_SCORE]
                if len(relevant) < len(scored_docs):
                    logger.info(f"Dropped {len(scored_docs) - len(relevant)} chunks graded below {RERANK_MIN_SCORE}/10.")
                return relevant[:top_k]
        except Exception as e:
            logger.error(f"Error during LLM re-ranking: {e}")
            
        # Fallback to index order
        return [(doc, 1.0 - (idx * 0.05)) for idx, doc in enumerate(candidates[:top_k])]

    def _clean_search_query(self, query: str) -> str:
        """Simplifies the search query for search engine compatibility."""
        cleaned = clean_search_query(query)
        logger.info(f"Simplified query for Web Search: '{query}' ➔ '{cleaned}'")
        return cleaned

    def web_search_fallback(self, query: str, max_results: int = 3, clean: bool = True) -> List[Dict[str, Any]]:
        """Fetches real-time snippets from the web to ground answers the local corpus can't.

        Previously this scraped Yahoo first and only fell back to DuckDuckGo. Yahoo now
        redirects automated requests into a bot-verification endpoint that ends in a 500,
        so every search burned two failed attempts plus their retry sleeps - several
        seconds - before reaching the fallback that was doing the actual work.
        """
        clean_q = self._clean_search_query(query) if clean else query
        logger.info(f"Triggering live web search for query: '{clean_q}'")
        results = []
        
        # DuckDuckGo throttles bursts, so a query fired alongside others often raises on
        # the first try and succeeds moments later. Retry once on error (but not on an
        # empty result, which is a real answer and shouldn't cost another round trip).
        for attempt in range(2):
            try:
                with DDGS() as ddgs:
                    for r in ddgs.text(clean_q, max_results=max_results):
                        results.append({
                            "title": r.get("title", ""),
                            "body": r.get("body", ""),
                            "href": r.get("href", "")
                        })
                if results:
                    logger.info(f"Retrieved {len(results)} web results for '{clean_q}'.")
                else:
                    logger.warning(f"Web search returned no results for '{clean_q}'.")
                break
            except Exception as e:
                results = []
                if attempt == 0:
                    logger.warning(f"Web search for '{clean_q}' failed ({e}); retrying once.")
                    time.sleep(1.5)
                else:
                    logger.error(f"Web search failed for '{clean_q}': {e}")

        return results

    def generate_tactical_analysis(
        self, 
        query: str, 
        top_k: int = None, 
        temperature: float = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates the entire RAG pipeline:
        1. Follow-up questions are condensed into standalone ones using `history`
        2. Live Intent Check -> Fetch and Prepend BBC Sport live scores/news if needed
        3. Query expansion -> hybrid (FAISS + BM25) retrieval per query, fused with RRF
        4. LLM re-ranking; chunks graded irrelevant are dropped
        5. Web search fallback when the local corpus doesn't cover the question
        6. Format Context & System/User Prompts (with recent conversation turns)
        7. Call the LLM and return the response plus source audits
        """
        # Explicit None checks: a requested temperature of 0.0 is valid
        top_k = top_k if top_k is not None else settings.RETRIEVAL_TOP_K
        temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        history = [
            {"role": turn.get("role"), "content": str(turn.get("content") or "")}
            for turn in (history or [])
            if turn.get("role") in ("user", "assistant") and turn.get("content")
        ][-HISTORY_MAX_TURNS:]

        if self.openai_client is None:
            self.initialize_openai()

        search_query = self._condense_query(query, history)

        # 1. Live scores / news for questions about what's happening now
        is_live_matches_active = False
        live_context = ""
        if is_live_intent(search_query):
            logger.info("Live football match/news intent detected. Fetching live feed...")
            try:
                from backend.loaders.live_score_loader import fetch_live_football_feed, get_live_scores_context
                if fetch_live_football_feed():
                    live_context = get_live_scores_context()
                    is_live_matches_active = True
                else:
                    logger.warning("Live feed returned no items; not using it as context.")
            except Exception as e:
                logger.error(f"Failed to fetch live scores context in RAG: {str(e)}")

        # Query local historical SQLite matches
        historical_context = retrieve_historical_matches_context(search_query)

        # 2. Hybrid search (FAISS + BM25) for each expanded query, fused with RRF
        logger.info(f"Running Hybrid Search with Query Expansion for query: '{search_query}'")
        queries = self._expand_query(search_query)

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

        ranked_lists = []
        for q in queries:
            ranked_lists.append(self.retrieve_context(q, top_k * 3))
            if self.bm25_searcher is not None:
                try:
                    ranked_lists.append(self.bm25_searcher.search(q, top_k * 3))
                except Exception as e:
                    logger.error(f"Error searching BM25 index for query '{q}': {str(e)}")

        fused_candidates = reciprocal_rank_fusion(ranked_lists, top_k=top_k * 3)
        candidate_docs = [doc for doc, score in fused_candidates]

        # 3. LLM-Based Re-ranking to extract the top-k highest-quality chunks
        retrieved_results = self._llm_rerank(search_query, candidate_docs, top_k)

        logger.info(f"Query Expansion & Hybrid Search retrieved {len(candidate_docs)} candidates; LLM Re-ranking selected top-{len(retrieved_results)} chunks.")

        # Evaluate local matching quality (relying on dense vector score of the original query)
        is_local_rag_sufficient = False
        original_dense = self.retrieve_context(search_query, 1)
        if original_dense and retrieved_results:
            max_dense_score = original_dense[0][1]
            if max_dense_score >= settings.RAG_SIMILARITY_THRESHOLD:
                is_local_rag_sufficient = True

        # 3. Web search fallback when the local corpus doesn't cover the question.
        #    The live feed is only today's BBC scores/headlines, so it doesn't stand in
        #    for a web search on anything else.
        is_web_search_active = False
        web_results = []
        if settings.WEB_SEARCH_ENABLED and not is_local_rag_sufficient:
            logger.info(f"Local RAG dense matches insufficient (max dense score: {original_dense[0][1] if original_dense else 0.0:.3f} < threshold: {settings.RAG_SIMILARITY_THRESHOLD}). Executing live search.")
            web_results = self.web_search_fallback(search_query, max_results=3)
            if web_results:
                is_web_search_active = True

        # 4. Format Context and Source Audits
        formatted_context_list = []
        sources = []
        is_rag_active = len(retrieved_results) > 0 or is_web_search_active or is_live_matches_active or bool(historical_context)
        
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
        if search_query != query:
            user_prompt += f"\n(Interpreted in the context of the conversation as: {search_query})\n"

        # Earlier turns so follow-ups are answered in context. Retrieved context is only
        # attached to the current question; old answers are trimmed to bound the prompt.
        history_messages = [
            {"role": turn["role"], "content": turn["content"][:HISTORY_MAX_CHARS_PER_TURN]}
            for turn in history
        ]

        # 6. Generate response via OpenAI (or fallback to Mock)
        response_text = ""
        is_mock = False

        if self.openai_client is not None:
            try:
                completion = self.openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        *history_messages,
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
            
        # Append disclaimer note if not grounded in RAG (the system prompt asks the LLM
        # to add its own, so don't print it twice)
        if not is_rag_active and "RAG Grounding Note" not in response_text:
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
