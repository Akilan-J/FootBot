import sys
from pathlib import Path

# Add project root to python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.database import save_historical_match

def main():
    print("Inserting Argentina vs Iceland match...")
    save_historical_match(
        home="Argentina",
        away="Iceland",
        home_score=3,
        away_score=0,
        date_str="2026-06-10",
        league="World Cup"
    )
    print("Match successfully saved to database.")

if __name__ == "__main__":
    main()
