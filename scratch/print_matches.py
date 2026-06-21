import sqlite3

conn = sqlite3.connect("data/footbot.db")
cursor = conn.cursor()

# Get table info/schema
cursor.execute("PRAGMA table_info(historical_matches);")
columns = cursor.fetchall()
print("Table Schema:")
for col in columns:
    print(f"  {col[1]} ({col[2]})")

# Retrieve matches
cursor.execute("SELECT id, home_team, away_team, home_score, away_score, match_date, league FROM historical_matches;")
rows = cursor.fetchall()
print(f"\nTotal Matches: {len(rows)}")
for r in rows:
    print(f"ID: {r[0]} | {r[1]} {r[3]}-{r[4]} {r[2]} | Date: {r[5]} | League: {r[6]}")

conn.close()
