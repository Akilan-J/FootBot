import os
import logging
import datetime
from pathlib import Path
from backend.config import settings


def bbc_today() -> datetime.date:
    """Today's date as BBC Sport means it: UK time. Its undated scores page and the
    "Today" it prints are UK dates, so reading them with the machine's own date
    (IST is up to 5.5 hours ahead) filed evening matches under the next day."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Europe/London")).date()
    except Exception:
        # No timezone database available: UTC is at most an hour off UK time
        return datetime.datetime.now(datetime.timezone.utc).date()

def setup_logging(name: str = "footbot") -> logging.Logger:
    """Configures and returns a standardized logger for all FootBot modules."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Console Handler
        c_handler = logging.StreamHandler()
        c_handler.setLevel(logging.INFO)
        
        # Formatting
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        c_handler.setFormatter(formatter)
        logger.addHandler(c_handler)
        
    return logger

logger = setup_logging()

def ensure_directories():
    """Ensures that all configured data directories exist on disk."""
    directories = [
        settings.RAW_DATA_PATH,
        settings.PROCESSED_DATA_PATH,
        settings.FAISS_DB_PATH
    ]
    
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {path}")

def is_vector_db_ready() -> bool:
    """Checks if the FAISS vector database index has been built and saved."""
    db_path = settings.FAISS_DB_PATH
    # FAISS writes two files: index.faiss and index.pkl
    faiss_file = db_path / "index.faiss"
    pkl_file = db_path / "index.pkl"
    return faiss_file.exists() and pkl_file.exists()
