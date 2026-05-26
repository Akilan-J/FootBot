import sqlite3
import json
import uuid
import hashlib
import os
from typing import List, Dict, Any, Optional, Tuple
from backend.config import settings
from backend.utils import logger

# Absolute path to the database file
DB_PATH = settings.RAW_DATA_PATH.parent / "footbot.db"

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Returns dictionaries instead of tuples
    return conn

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hashes a password utilizing secure PBKDF2 HMAC algorithm."""
    s = salt or os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        s.encode('utf-8'),
        100000
    ).hex()
    return pwd_hash, s

def verify_password(password: str, pwd_hash: str, salt: str) -> bool:
    """Verifies a password against its recorded PBKDF2 hash."""
    check_hash, _ = hash_password(password, salt)
    return check_hash == pwd_hash

def init_db() -> None:
    """Initializes the database schema by creating required tables if missing."""
    logger.info(f"Initializing SQLite database at: {DB_PATH}")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create Sessions table (with foreign key to users)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
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
        
        # Create Historical Matches table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                home_score INTEGER,
                away_score INTEGER,
                match_date TEXT NOT NULL,
                league TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        
        # Defensive Migration: Check if user_id column exists in sessions table
        try:
            cursor.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
            conn.commit()
            logger.info("Migrated sessions table: user_id column added successfully.")
        except sqlite3.OperationalError:
            # Column already exists
            pass
            
        logger.info("SQLite database schema successfully compiled.")
    except Exception as e:
        logger.error(f"Failed to initialize SQLite database: {str(e)}")
    finally:
        conn.close()

def register_user(username: str, password: str) -> Optional[str]:
    """Registers a new user and returns their unique identifier."""
    conn = get_db_connection()
    cursor = conn.cursor()
    uid = str(uuid.uuid4())
    pwd_hash, salt = hash_password(password)
    
    try:
        cursor.execute(
            "INSERT INTO users (id, username, password_hash, salt) VALUES (?, ?, ?, ?)",
            (uid, username.strip(), pwd_hash, salt)
        )
        conn.commit()
        logger.info(f"Successfully registered user: '{username}' (ID: {uid})")
        return uid
    except sqlite3.IntegrityError:
        logger.warning(f"Registration failed: username '{username}' already exists.")
        return None
    except Exception as e:
        logger.error(f"Error registering user: {str(e)}")
        return None
    finally:
        conn.close()

def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticates a user and returns their profile details if successful."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT id, username, password_hash, salt FROM users WHERE username = ?",
            (username.strip(),)
        )
        row = cursor.fetchone()
        if row:
            if verify_password(password, row["password_hash"], row["salt"]):
                logger.info(f"Successful authentication for user: '{username}'")
                return {"id": row["id"], "username": row["username"]}
        logger.warning(f"Failed authentication attempt for user: '{username}'")
        return None
    except Exception as e:
        logger.error(f"Error authenticating user: {str(e)}")
        return None
    finally:
        conn.close()

def create_session(title: str, user_id: str, session_id: Optional[str] = None) -> str:
    """Creates a new session for a user and returns its unique identifier."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sid = session_id or str(uuid.uuid4())
    try:
        cursor.execute(
            "INSERT INTO sessions (id, user_id, title) VALUES (?, ?, ?)",
            (sid, user_id, title)
        )
        conn.commit()
        logger.info(f"Created new database session: '{title}' (User ID: {user_id}, Session ID: {sid})")
    except Exception as e:
        logger.error(f"Failed to create session in database: {str(e)}")
    finally:
        conn.close()
        
    return sid

def verify_session_owner(session_id: str, user_id: str) -> bool:
    """Verifies that a session belongs to a specific user, returning True if so."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id)
        )
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error verifying session owner: {str(e)}")
        return False
    finally:
        conn.close()


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

def get_sessions(user_id: str) -> List[Dict[str, Any]]:
    """Retrieves all chat sessions for a specific user, sorted by date."""
    conn = get_db_connection()
    cursor = conn.cursor()
    results = []
    
    try:
        cursor.execute(
            "SELECT id, title, created_at FROM sessions WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        rows = cursor.fetchall()
        for r in rows:
            results.append({
                "id": r["id"],
                "title": r["title"],
                "created_at": r["created_at"]
            })
    except Exception as e:
        logger.error(f"Failed to fetch sessions for user {user_id}: {str(e)}")
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

def save_historical_match(home: str, away: str, home_score: Optional[int], away_score: Optional[int], date_str: str, league: str) -> None:
    """Saves a historical match scoreline to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Prevent duplicates by checking if the exact match on this date already exists
        cursor.execute("""
            SELECT id FROM historical_matches 
            WHERE home_team = ? AND away_team = ? AND match_date = ?
        """, (home, away, date_str))
        if cursor.fetchone():
            return
            
        cursor.execute("""
            INSERT INTO historical_matches (home_team, away_team, home_score, away_score, match_date, league)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (home, away, home_score, away_score, date_str, league))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to save historical match: {str(e)}")
    finally:
        conn.close()

def get_historical_matches(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves saved historical matches."""
    conn = get_db_connection()
    cursor = conn.cursor()
    results = []
    
    try:
        cursor.execute("""
            SELECT home_team, away_team, home_score, away_score, match_date, league 
            FROM historical_matches 
            ORDER BY created_at DESC LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        for r in rows:
            results.append({
                "home_team": r["home_team"],
                "away_team": r["away_team"],
                "home_score": r["home_score"],
                "away_score": r["away_score"],
                "match_date": r["match_date"],
                "league": r["league"]
            })
    except Exception as e:
        logger.error(f"Failed to fetch historical matches: {str(e)}")
    finally:
        conn.close()
        
    return results

def search_historical_matches(team_name: str) -> List[Dict[str, Any]]:
    """Searches historical matches involving a specific team name."""
    conn = get_db_connection()
    cursor = conn.cursor()
    results = []
    
    try:
        pattern = f"%{team_name.strip()}%"
        cursor.execute("""
            SELECT home_team, away_team, home_score, away_score, match_date, league 
            FROM historical_matches 
            WHERE home_team LIKE ? OR away_team LIKE ? OR league LIKE ?
            ORDER BY created_at DESC LIMIT 30
        """, (pattern, pattern, pattern))
        rows = cursor.fetchall()
        for r in rows:
            results.append({
                "home_team": r["home_team"],
                "away_team": r["away_team"],
                "home_score": r["home_score"],
                "away_score": r["away_score"],
                "match_date": r["match_date"],
                "league": r["league"]
            })
    except Exception as e:
        logger.error(f"Failed to search historical matches for {team_name}: {str(e)}")
    finally:
        conn.close()
        
    return results

if __name__ == "__main__":
    init_db()
