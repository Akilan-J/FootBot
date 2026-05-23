import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve project root path
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from project root
dotenv_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=dotenv_path)

class Settings:
    """Centralized application settings with environment variable bindings and defaults."""
    
    # OpenAI API configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL_NAME: str = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))

    # RAG parameters
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
    RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", "4"))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    
    # Web search parameters
    WEB_SEARCH_ENABLED: bool = os.getenv("WEB_SEARCH_ENABLED", "True").lower() == "true"
    RAG_SIMILARITY_THRESHOLD: float = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.35"))

    # Path configurations (with dynamic absolute resolution)
    _raw_path: str = os.getenv("RAW_DATA_PATH", "data/raw")
    _processed_path: str = os.getenv("PROCESSED_DATA_PATH", "data/processed")
    _faiss_path: str = os.getenv("FAISS_DB_PATH", "data/embeddings")

    @property
    def RAW_DATA_PATH(self) -> Path:
        p = Path(self._raw_path)
        return p if p.is_absolute() else (BASE_DIR / p).resolve()

    @property
    def PROCESSED_DATA_PATH(self) -> Path:
        p = Path(self._processed_path)
        return p if p.is_absolute() else (BASE_DIR / p).resolve()

    @property
    def FAISS_DB_PATH(self) -> Path:
        p = Path(self._faiss_path)
        return p if p.is_absolute() else (BASE_DIR / p).resolve()

    # FastAPI settings
    FASTAPI_HOST: str = os.getenv("FASTAPI_HOST", "127.0.0.1")
    FASTAPI_PORT: int = int(os.getenv("FASTAPI_PORT", "8000"))

settings = Settings()
