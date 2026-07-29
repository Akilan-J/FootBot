import sqlite3
import json
import uuid
import hashlib
import os
import secrets
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
        
        # Create Auth Tokens table (opaque bearer session tokens, separate from the permanent user id)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)

        # Create API-Football Team Mapping table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_football_teams (
                team_name TEXT PRIMARY KEY,
                api_id INTEGER NOT NULL
            )
        """)

        # Create API-Football Fixture Mapping table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_football_fixtures (
                home_team TEXT,
                away_team TEXT,
                match_date TEXT,
                fixture_id INTEGER NOT NULL,
                PRIMARY KEY (home_team, away_team, match_date)
            )
        """)

        # Create Indexes for optimization
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_historical_matches_teams ON historical_matches(home_team, away_team)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_football_teams_name ON api_football_teams(team_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_football_fixtures_match ON api_football_fixtures(home_team, away_team, match_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_tokens_user_id ON auth_tokens(user_id)")
        
        conn.commit()
        
        # Defensive Migration: Check if user_id column exists in sessions table
        try:
            cursor.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
            conn.commit()
            logger.info("Migrated sessions table: user_id column added successfully.")
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # One-time seed: pre-existing chat sessions were stored under the literal
        # user_id "default_coach" (the frontend's hardcoded pseudo-identity, back when
        # X-User-Token was the raw user id). Seed that id as a real user row so the
        # frontend can log in and keep reaching that history via a minted session token.
        # Only runs if FOOTBOT_LEGACY_DEMO_PASSWORD is explicitly set — there is no
        # baked-in default password for this account.
        if settings.LEGACY_DEMO_PASSWORD:
            try:
                cursor.execute("SELECT id FROM users WHERE id = ?", (settings.LEGACY_DEMO_USERNAME,))
                if not cursor.fetchone():
                    pwd_hash, salt = hash_password(settings.LEGACY_DEMO_PASSWORD)
                    cursor.execute(
                        "INSERT INTO users (id, username, password_hash, salt) VALUES (?, ?, ?, ?)",
                        (settings.LEGACY_DEMO_USERNAME, settings.LEGACY_DEMO_USERNAME, pwd_hash, salt)
                    )
                    conn.commit()
                    logger.info(f"Seeded legacy demo account '{settings.LEGACY_DEMO_USERNAME}' to preserve pre-existing chat history.")
            except sqlite3.IntegrityError:
                # Username collision with an already-registered real account; nothing to do.
                pass
        else:
            logger.warning(
                "FOOTBOT_LEGACY_DEMO_PASSWORD is not set: the legacy 'default_coach' demo "
                "account was not seeded, so any pre-existing chat history stored under that "
                "user id will be unreachable until it is set and the server is restarted."
            )

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

def create_session_token(user_id: str, ttl_seconds: Optional[int] = None) -> str:
    """Mints a new opaque, random bearer token for a user and stores it with an expiry.
    This token (not the user's DB row id) is what gets handed to the client as X-User-Token.
    Each call adds a new row rather than replacing prior ones, so a user can hold several
    valid tokens at once (e.g. multiple devices/browsers) - each independently revocable
    via /logout."""
    conn = get_db_connection()
    cursor = conn.cursor()
    token = secrets.token_urlsafe(32)
    ttl = ttl_seconds if ttl_seconds is not None else settings.SESSION_TOKEN_TTL_SECONDS

    try:
        cursor.execute(
            "INSERT INTO auth_tokens (token, user_id, expires_at) VALUES (?, ?, datetime('now', ?))",
            (token, user_id, f"{ttl:+d} seconds")
        )
        conn.commit()
        logger.info(f"Issued new session token for user ID: {user_id}")
    finally:
        conn.close()

    return token

def resolve_session_token(token: str) -> Optional[str]:
    """Resolves an opaque session token to its owning user id, or None if it is missing/expired.
    Expired tokens are deleted on lookup rather than kept around."""
    if not token:
        return None

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT user_id, expires_at, (expires_at < datetime('now')) AS is_expired FROM auth_tokens WHERE token = ?",
            (token,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        if row["is_expired"]:
            cursor.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
            conn.commit()
            logger.info("Session token expired and was removed.")
            return None

        return row["user_id"]
    except Exception as e:
        logger.error(f"Error resolving session token: {str(e)}")
        return None
    finally:
        conn.close()

def delete_session_token(token: str) -> None:
    """Revokes a session token (logout). Deleting a token that doesn't exist is a no-op."""
    if not token:
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
        conn.commit()
    except Exception as e:
        logger.error(f"Error deleting session token: {str(e)}")
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
    """Saves a historical match scoreline to the database, updating scores if they changed, and preventing duplicates."""
    import re
    import datetime

    def parse_date_from_str(s: str) -> Optional[datetime.date]:
        months = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        m = re.search(r'(\d{1,2})\s+([a-zA-Z]{3,})\s+(\d{4})', s)
        if m:
            day = int(m.group(1))
            month_name = m.group(2).lower()[:3]
            year = int(m.group(3))
            if month_name in months:
                try:
                    return datetime.date(year, months[month_name], day)
                except ValueError:
                    pass
        return None

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Fetch existing matches for these two teams
        cursor.execute("""
            SELECT id, home_score, away_score, match_date, league FROM historical_matches 
            WHERE LOWER(home_team) = LOWER(?) AND LOWER(away_team) = LOWER(?)
        """, (home.strip(), away.strip()))
        
        rows = cursor.fetchall()
        matched_id = None
        existing_row = None
        
        new_date_obj = parse_date_from_str(date_str)
        
        for r in rows:
            exist_id = r["id"]
            exist_date_str = r["match_date"]
            exist_date_obj = parse_date_from_str(exist_date_str)
            
            # Check if they are the same match
            is_same = False
            if new_date_obj and exist_date_obj:
                if abs((new_date_obj - exist_date_obj).days) <= 2:
                    is_same = True
            else:
                # If one or both don't have a calendar date, check substring match or text match
                s1 = date_str.lower().strip()
                s2 = exist_date_str.lower().strip()
                if s1 in s2 or s2 in s1:
                    is_same = True
                elif not new_date_obj and not exist_date_obj:
                    # Both are just group names/etc.
                    is_same = True
            
            if is_same:
                matched_id = exist_id
                existing_row = r
                break
                
        if matched_id is not None:
            # We found a match! Check if we need to update the scores or the date/league
            exist_hs = existing_row["home_score"]
            exist_as = existing_row["away_score"]
            exist_date_str = existing_row["match_date"]
            
            # Determine if new date has more details (e.g. contains calendar date while existing one doesn't)
            exist_has_cal = parse_date_from_str(exist_date_str) is not None
            new_has_cal = new_date_obj is not None
            
            updated_date = exist_date_str
            if new_has_cal and not exist_has_cal:
                updated_date = date_str
            elif len(date_str) > len(exist_date_str) and (new_has_cal == exist_has_cal):
                updated_date = date_str
                
            # Update if scores changed or if we got more detailed date
            if home_score != exist_hs or away_score != exist_as or updated_date != exist_date_str:
                cursor.execute("""
                    UPDATE historical_matches 
                    SET home_score = ?, away_score = ?, match_date = ?, league = ?
                    WHERE id = ?
                """, (home_score, away_score, updated_date, league, matched_id))
                conn.commit()
                logger.info(f"Updated match {home} vs {away} to {home_score}-{away_score} (Date: {updated_date})")
        else:
            # No match found, insert new record
            cursor.execute("""
                INSERT INTO historical_matches (home_team, away_team, home_score, away_score, match_date, league)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (home, away, home_score, away_score, date_str, league))
            conn.commit()
            logger.info(f"Inserted new match {home} vs {away} ({home_score}-{away_score})")
            
    except Exception as e:
        logger.error(f"Failed to save/update historical match: {str(e)}")
    finally:
        conn.close()

def get_historical_matches(limit: int = 1000) -> List[Dict[str, Any]]:
    """Retrieves saved historical matches, filtering out women's matches."""
    conn = get_db_connection()
    cursor = conn.cursor()
    results = []
    
    try:
        cursor.execute("""
            SELECT home_team, away_team, home_score, away_score, match_date, league 
            FROM historical_matches 
            WHERE NOT (home_team LIKE '%women%' OR away_team LIKE '%women%' OR league LIKE '%women%')
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
    """Searches historical matches involving a specific team name, filtering out women's matches."""
    conn = get_db_connection()
    cursor = conn.cursor()
    results = []
    
    try:
        pattern = f"%{team_name.strip()}%"
        cursor.execute("""
            SELECT home_team, away_team, home_score, away_score, match_date, league 
            FROM historical_matches 
            WHERE (home_team LIKE ? OR away_team LIKE ? OR league LIKE ?)
              AND NOT (home_team LIKE '%women%' OR away_team LIKE '%women%' OR league LIKE '%women%')
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

def get_api_team_id(team_name: str) -> Optional[int]:
    """Retrieves cached API-Football team ID for a team name (case-insensitive)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT api_id FROM api_football_teams WHERE LOWER(team_name) = LOWER(?)",
            (team_name.strip(),)
        )
        row = cursor.fetchone()
        return row["api_id"] if row else None
    except Exception as e:
        logger.error(f"Error getting api team id: {e}")
        return None
    finally:
        conn.close()

def save_api_team_id(team_name: str, api_id: int) -> None:
    """Caches API-Football team ID for a team name."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO api_football_teams (team_name, api_id) VALUES (?, ?)",
            (team_name.strip(), api_id)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Error saving api team id: {e}")
    finally:
        conn.close()

def get_api_fixture_id(home: str, away: str, date: str) -> Optional[int]:
    """Retrieves cached API-Football fixture ID (case-insensitive, normalized date)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT fixture_id FROM api_football_fixtures WHERE LOWER(home_team) = LOWER(?) AND LOWER(away_team) = LOWER(?) AND LOWER(match_date) = LOWER(?)",
            (home.strip(), away.strip(), date.strip())
        )
        row = cursor.fetchone()
        return row["fixture_id"] if row else None
    except Exception as e:
        logger.error(f"Error getting api fixture id: {e}")
        return None
    finally:
        conn.close()

def save_api_fixture_id(home: str, away: str, date: str, fixture_id: int) -> None:
    """Caches API-Football fixture ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO api_football_fixtures (home_team, away_team, match_date, fixture_id) VALUES (?, ?, ?, ?)",
            (home.strip(), away.strip(), date.strip(), fixture_id)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Error saving api fixture id: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
