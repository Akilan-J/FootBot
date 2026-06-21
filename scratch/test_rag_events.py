import logging
import json
import sys

from backend.roster_store import fetch_real_world_match_events_via_rag

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_extraction():
    print("=================== TEST 1: Portugal vs Congo DR (17 Jun 2026) ===================")
    goals = fetch_real_world_match_events_via_rag("Portugal", "Congo DR", "17 Jun 2026")
    print("Resulting Goal Events:")
    print(json.dumps(goals, indent=2))
    
    # Simple validation
    assert goals is not None, "Goals list should not be None"
    assert len(goals) > 0, "Should find goals for the match"
    
    scorers = {g["scorer"] for g in goals}
    assert "João Neves" in scorers or "Neves" in "".join(scorers), "João Neves should be in scorers"
    assert "Yoane Wissa" in scorers or "Wissa" in "".join(scorers), "Yoane Wissa should be in scorers"
    print("Assertion passed: Successfully extracted real goalscorers!")

if __name__ == "__main__":
    test_extraction()
