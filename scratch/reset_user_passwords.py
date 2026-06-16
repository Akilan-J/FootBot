import sqlite3
from backend.database import DB_PATH, hash_password

def reset_passwords():
    print(f"Connecting to database at {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    users = ["Akilan", "pep.guardiola"]
    new_password = "password123"
    
    for username in users:
        pwd_hash, salt = hash_password(new_password)
        cursor.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE username = ?",
            (pwd_hash, salt, username)
        )
        print(f"Updated password for user '{username}' to '{new_password}'")
        
    conn.commit()
    conn.close()
    print("Database update complete.")

if __name__ == "__main__":
    reset_passwords()
