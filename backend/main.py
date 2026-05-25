import os
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.config import settings
from backend.utils import logger, ensure_directories, is_vector_db_ready
from backend.rag_engine import rag_engine
from backend.ingest import run_ingestion

# Initialize directories on start
ensure_directories()

app = FastAPI(
    title="FootBot ⚽🤖",
    description="Production-Grade Generative AI & RAG Football Tactics Analysis Platform Backend",
    version="1.0.0"
)

# CORS Configuration - enables Streamlit frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to Streamlit's specific origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Data Models ---

class ChatRequest(BaseModel):
    query: str = Field(
        ..., 
        description="The football tactical query to analyze.", 
        example="Compare Sergio Busquets and Rodri in spatial discipline"
    )
    temperature: Optional[float] = Field(
        default=None, 
        description="LLM temperature parameter (between 0.0 and 1.0).",
        ge=0.0,
        le=1.0
    )
    top_k: Optional[int] = Field(
        default=None, 
        description="Number of relevant document chunks to retrieve.",
        gt=0,
        le=10
    )

class SourceDocSchema(BaseModel):
    index: int
    text: str
    source: str
    page: Optional[int] = None
    type: str
    score: float

class ChatResponse(BaseModel):
    query: str
    response: str
    is_rag_active: bool
    is_web_search_active: bool
    is_live_matches_active: bool
    is_mock: bool
    sources: List[SourceDocSchema]

class UrlIngestRequest(BaseModel):
    url: str = Field(..., description="The remote web page URL to crawl and index.", example="https://spielverlagerung.com/2021/05/22/tactical-analysis-guardiolas-inverted-fullbacks/")

class IngestResponse(BaseModel):
    status: str
    total_files_processed: Optional[int] = None
    total_chunks_indexed: Optional[int] = None
    message: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    vector_db_loaded: bool
    openai_initialized: bool
    openai_model: str

# --- Endpoints ---

@app.get("/", status_code=status.HTTP_200_OK)
def root():
    return {
        "app": "FootBot Backend Server",
        "status": "online",
        "docs_url": "/docs"
    }

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Returns the operational health status of the RAG engine and API keys."""
    vector_ready = is_vector_db_ready()
    # Try loading FAISS if not already loaded
    if vector_ready and rag_engine.vector_store is None:
        rag_engine.load_vector_db()
        
    return {
        "status": "healthy",
        "vector_db_loaded": rag_engine.vector_store is not None,
        "openai_initialized": rag_engine.openai_client is not None,
        "openai_model": settings.OPENAI_MODEL_NAME
    }

@app.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat_endpoint(request: ChatRequest):
    """
    Accepts a tactical query, runs it through the RAG engine, 
    and returns tactical insights with citations.
    """
    logger.info(f"Received chat query: '{request.query}'")
    if not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query content cannot be blank or whitespace."
        )
        
    try:
        # Run synchronous RAG engine in separate thread pool for FastAPI async concurrency
        analysis_result = rag_engine.generate_tactical_analysis(
            query=request.query,
            top_k=request.top_k,
            temperature=request.temperature
        )
        return analysis_result
    except Exception as e:
        logger.error(f"Error during chat generation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred generating your tactical analysis: {str(e)}"
        )

@app.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_200_OK)
async def ingest_endpoint():
    """
    Triggers document scanning, parsing, text splitting, embedding generation, 
    and FAISS vector database compilation. Dynamically reloads the active index.
    """
    logger.info("Manual ingestion triggered via API.")
    try:
        # Run ingestion
        result = run_ingestion()
        
        if result["status"] == "success":
            # Force reload of FAISS database in-memory to ensure immediate query availability
            logger.info("Hot-reloading FAISS database in RAG engine...")
            reload_status = rag_engine.load_vector_db(force_reload=True)
            
            if reload_status:
                return {
                    "status": "success",
                    "total_files_processed": result.get("total_files_processed"),
                    "total_chunks_indexed": result.get("total_chunks_indexed"),
                    "message": "Documents successfully ingested and database index hot-reloaded!"
                }
            else:
                return {
                    "status": "success",
                    "total_files_processed": result.get("total_files_processed"),
                    "total_chunks_indexed": result.get("total_chunks_indexed"),
                    "message": "Documents processed, but engine failed to hot-reload FAISS index. Restart server recommended."
                }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Ingestion failed.")
            )
            
    except Exception as e:
        logger.error(f"Error during API-triggered ingestion: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion pipeline failed: {str(e)}"
        )

@app.post("/ingest/url", response_model=IngestResponse, status_code=status.HTTP_200_OK)
async def ingest_url_endpoint(request: UrlIngestRequest):
    """
    Downloads, crawls, cleans, chunks, and indexes a dynamic web article URL into the FAISS database in real-time.
    """
    logger.info(f"Dynamic web ingestion triggered for URL: '{request.url}'")
    try:
        from backend.loaders.blog_loader import load_blog_from_url
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        # 1. Fetch and crawl the remote URL
        docs = load_blog_from_url(request.url)
        if not docs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to crawl and extract clean text from the provided URL. Ensure it is accessible."
            )
            
        # 2. Segment document
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )
        chunks = text_splitter.split_documents(docs)
        logger.info(f"Split scraped webpage into {len(chunks)} overlapping chunks.")
        
        # 3. Add to existing index, or compile a new one
        if rag_engine.vector_store is not None:
            rag_engine.vector_store.add_documents(chunks)
            logger.info("Added new chunks to existing in-memory FAISS database.")
            # Save FAISS index locally
            rag_engine.vector_store.save_local(str(settings.FAISS_DB_PATH))
            logger.info(f"Saved updated FAISS index to: {settings.FAISS_DB_PATH}")
        else:
            logger.info("FAISS index does not exist. Creating a fresh index with scraped URL data...")
            from langchain_community.vectorstores import FAISS
            from langchain_community.embeddings import HuggingFaceEmbeddings
            embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL_NAME)
            db = FAISS.from_documents(chunks, embeddings)
            db.save_local(str(settings.FAISS_DB_PATH))
            logger.info(f"Created and saved fresh FAISS index to: {settings.FAISS_DB_PATH}")
            
        # 4. Perform dynamic in-memory hot-reload
        rag_engine.load_vector_db(force_reload=True)
        
        return {
            "status": "success",
            "total_files_processed": 1,
            "total_chunks_indexed": len(chunks),
            "message": f"Successfully scraped, segmented, and hot-indexed {len(chunks)} chunks into active memory!"
        }
    except Exception as e:
        logger.error(f"Failed dynamic URL ingestion: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"URL crawler pipeline execution failed: {str(e)}"
        )

@app.get("/live-matches", status_code=status.HTTP_200_OK)
def live_matches_endpoint():
    """
    Crawls the latest live football match scores, breaking transfer news, 
    and updates from public RSS feeds.
    """
    logger.info("Live matches endpoint queried.")
    try:
        from backend.loaders.live_score_loader import fetch_live_football_feed
        feed = fetch_live_football_feed()
        return {
            "status": "success",
            "count": len(feed),
            "feed": feed
        }
    except Exception as e:
        logger.error(f"Error serving live matches: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to crawl live matches: {str(e)}"
        )
