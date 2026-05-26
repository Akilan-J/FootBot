import sqlite3
import json
import uuid
from typing import List, Dict, Any, Optional
from backend.config import settings
from backend.utils import logger

# Absolute path to the database file
DB_PATH = settings.RAW_DATA_PATH.parent / "footbot.db"

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Returns dictionaries instead of tuples
    return conn

def init_db() -> None:
    """Initializes the database schema by creating required tables if missing."""
    logger.info(f"Initializing SQLite database at: {DB_PATH}")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()
        logger.info("SQLite database schema successfully compiled.")
    except Exception as e:
        logger.error(f"Failed to initialize SQLite database: {str(e)}")
    finally:
        conn.close()

def create_session(title: str, session_id: Optional[str] = None) -> str:
    """Creates a new session and returns its unique identifier."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sid = session_id or str(uuid.uuid4())
    try:
        cursor.execute(
            "INSERT INTO sessions (id, title) VALUES (?, ?)",
            (sid, title)
        )
        conn.commit()
        logger.info(f"Created new database session: '{title}' (ID: {sid})")
    except Exception as e:
        logger.error(f"Failed to create session in database: {str(e)}")
    finally:
        conn.close()
        
    return sid

def save_message(session_id: str, role: str, content: str, sources: List[Dict[str, Any]]) -> None:
    """Saves a message (and its serialized citations) to a session."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Serialize sources to JSON string
    sources_json = json.dumps(sources) if sources else "[]"
    
    try:
        cursor.execute(
            "INSERT INTO messages (session_id, role, content, sources) VALUES (?, ?, ?, ?)",
            (session_id, role, content, sources_json)
        )
        conn.commit()
        logger.debug(f"Saved message ({role}) to session ID: {session_id}")
    except Exception as e:
        logger.error(f"Failed to save message to database: {str(e)}")
    finally:
        conn.close()

def get_sessions() -> List[Dict[str, Any]]:
    """Retrieves all chat sessions sorted by date."""
    conn = get_db_connection()
    cursor = conn.cursor()
    results = []
    
    try:
        cursor.execute("SELECT id, title, created_at FROM sessions ORDER BY created_at DESC")
        rows = cursor.fetchall()
        for r in rows:
            results.append({
                "id": r["id"],
                "title": r["title"],
                "created_at": r["created_at"]
            })
    except Exception as e:
        logger.error(f"Failed to fetch sessions: {str(e)}")
    finally:
        conn.close()
        
    return results

def get_messages(session_id: str) -> List[Dict[str, Any]]:
    """Retrieves all messages belonging to a specific session."""
    conn = get_db_connection()
    cursor = conn.cursor()
    results = []
    
    try:
        cursor.execute(
            "SELECT role, content, sources, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        )
        rows = cursor.fetchall()
        for r in rows:
            # Safely load JSON citations
            try:
                sources = json.loads(r["sources"]) if r["sources"] else []
            except Exception:
                sources = []
                
            results.append({
                "role": r["role"],
                "content": r["content"],
                "sources": sources,
                "created_at": r["created_at"]
            })
    except Exception as e:
        logger.error(f"Failed to fetch messages for session {session_id}: {str(e)}")
    finally:
        conn.close()
        
    return results

if __name__ == "__main__":
    init_db()
