import sqlite3

conn = sqlite3.connect("data/footbot.db")
cursor = conn.cursor()

cursor.execute("SELECT id, home_team, away_team, home_score, away_score, match_date FROM historical_matches WHERE home_score IS NULL OR away_score IS NULL;")
rows = cursor.fetchall()
print(f"Matches with NULL scores: {len(rows)}")
for r in rows:
    print(f"ID: {r[0]} | {r[1]} vs {r[2]} | Date: {r[5]}")

conn.close()
