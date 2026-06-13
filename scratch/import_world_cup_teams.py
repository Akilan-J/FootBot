import sys
import os
import json
import re
import ast
import traceback
from pathlib import Path

# Add workspace root to python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.roster_store import normalize_name, ensure_player_photos, load_cache, save_cache
from backend.rag_engine import rag_engine
from backend.utils import logger

# 48 teams participating in the 2026 FIFA World Cup
WORLD_CUP_TEAMS = [
    # Host Nations
    "Canada", "Mexico", "United States",
    # AFC (Asia)
    "Australia", "Iraq", "Iran", "Japan", "Jordan", "South Korea", "Qatar", "Saudi Arabia", "Uzbekistan",
    # CAF (Africa)
    "Algeria", "Cape Verde", "DR Congo", "Ivory Coast", "Egypt", "Ghana", "Morocco", "Senegal", "South Africa", "Tunisia",
    # Concacaf
    "Curacao", "Haiti", "Panama",
    # CONMEBOL
    "Argentina", "Brazil", "Colombia", "Ecuador", "Paraguay", "Uruguay",
    # OFC
    "New Zealand",
    # UEFA (Europe)
    "Austria", "Belgium", "Bosnia and Herzegovina", "Croatia", "Czech Republic", "England", "France", "Germany", "Netherlands", "Norway", "Portugal", "Scotland", "Spain", "Sweden", "Switzerland", "Turkey"
]

def fetch_roster_from_llm(team_name: str) -> list:
    """Queries LLM for a starting XI roster for a team."""
    prompt = f"""You are a professional football database helper. Your job is to return the actual, real-world current (or recent) starting XI lineup/squad for the football team '{team_name}'.
You must output exactly 11 players in JSON format.
Each player must have exactly the following keys:
- 'name': The real player's full name (e.g. 'Bukayo Saka' or 'A. Lunin')
- 'jersey': Their squad/jersey number as a string (e.g. '7')
- 'rating': A realistic SofaScore performance rating as a float between 6.0 and 9.5 (e.g. 7.4)
- 'pos': One of the standard tactical positions: 'GK', 'RB', 'RCB', 'LCB', 'LB', 'LDM', 'RDM', 'LCM', 'CM', 'RCM', 'LAM', 'CAM', 'RAM', 'LW', 'ST', 'RW', 'LST', 'RST', 'LM', 'RM', 'AM'. There must be exactly one 'GK' (goalkeeper).
- 'photo': Always an empty string ""
- 'age': The player's age as a string (e.g. '24')
- 'val': The player's market value as a string (e.g. '€120M' or '€5M')
- 'height': The player's height as a string (e.g. '178 cm')
- 'sofa_id': The player's official numerical Sofascore player ID as a string if known (e.g. '826725' for Erling Haaland, '40387' for Kevin De Bruyne). Guess a highly realistic numerical ID if you know it, otherwise return empty string "".

Return ONLY a raw valid JSON array. Do not write any markdown code wrappers (like ```json), notes, explanations, or extra characters. Simply return the raw JSON text. Make sure to double check that you are returning EXACTLY 11 players."""

    for attempt in range(1, 4):
        try:
            completion = rag_engine.openai_client.chat.completions.create(
                model=rag_engine.model_name,
                messages=[
                    {"role": "system", "content": "You are a database system returning raw JSON arrays only. Double check that you output exactly 11 players, one of which has position 'GK'."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3 + (attempt * 0.1)
            )
            response_text = completion.choices[0].message.content.strip()
            
            # Clean markdown wrappers if any
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            try:
                roster = json.loads(response_text)
            except Exception as json_err:
                logger.warning(f"Standard json.loads failed for '{team_name}' on attempt {attempt}: {json_err}. Attempting cleaning and ast.literal_eval...")
                import ast
                cleaned_text = response_text
                # strip markdown wrappers
                cleaned_text = re.sub(r"^```json\s*", "", cleaned_text)
                cleaned_text = re.sub(r"\s*```$", "", cleaned_text)
                cleaned_text = cleaned_text.strip()
                # Replace JSON literals with Python equivalents
                cleaned_text = cleaned_text.replace("true", "True").replace("false", "False").replace("null", "None")
                try:
                    roster = ast.literal_eval(cleaned_text)
                except Exception as ast_err:
                    logger.error(f"ast.literal_eval also failed for '{team_name}' on attempt {attempt}: {ast_err}")
                    raise json_err
            
            if isinstance(roster, list) and len(roster) == 11:
                # Validate structures
                valid = True
                required_keys = {"name", "jersey", "rating", "pos", "photo", "age", "val", "height", "sofa_id"}
                for p in roster:
                    if not required_keys.issubset(p.keys()):
                        valid = False
                        break
                
                if valid:
                    return roster
                else:
                    logger.warning(f"Attempt {attempt}: LLM returned JSON list for '{team_name}' but it was missing required player keys.")
            else:
                logger.warning(f"Attempt {attempt}: LLM did not return exactly 11 players for '{team_name}'. Length: {len(roster) if isinstance(roster, list) else 'not a list'}")
                
        except Exception as e:
            logger.error(f"Attempt {attempt} failed to query LLM for roster of '{team_name}': {e}")
            
        if attempt < 3:
            import time
            time.sleep(2.0)
            
    raise ValueError(f"Failed to fetch valid 11-player roster for '{team_name}' after 3 attempts.")

def main():
    print("Initializing OpenAI/OpenRouter connection...")
    rag_engine.initialize_openai()
    
    if rag_engine.openai_client is None:
        print("Error: OpenAI client not initialized. Make sure OPENAI_API_KEY is configured in .env.")
        sys.exit(1)
        
    print(f"Using LLM model: {rag_engine.model_name}")
    
    cache = load_cache()
    print(f"Current cache contains {len(cache)} teams.")
    
    # Normalize team keys for comparison
    normalized_cache_keys = {k: k for k in cache.keys()}
    
    success_count = 0
    skipped_count = 0
    failed_count = 0
    
    for team_name in WORLD_CUP_TEAMS:
        norm_name = normalize_name(team_name)
        
        # Check if the team name already matches a key in cache
        matched_key = None
        for k in normalized_cache_keys:
            if k == norm_name or k in norm_name or norm_name in k:
                matched_key = k
                break
                
        if matched_key:
            print(f"[-] Team '{team_name}' is already cached under '{matched_key}'. Skipping.")
            skipped_count += 1
            continue
            
        print(f"\n[+] Importing roster for '{team_name}'...")
        try:
            # Fetch roster from LLM
            roster = fetch_roster_from_llm(team_name)
            print(f"    Fetched roster of {len(roster)} players from LLM.")
            
            # Resolve player photos (downloading from FotMob/Wikipedia/etc. if needed)
            print(f"    Resolving and downloading player headshots for '{team_name}'...")
            ensure_player_photos(roster, team_name)
            
            # Update cache in memory and save to file
            cache = load_cache()  # reload to prevent overwriting updates if there's external activity
            cache[norm_name] = roster
            save_cache(cache)
            
            # Refresh our tracking set
            normalized_cache_keys[norm_name] = norm_name
            
            print(f"    Successfully imported and cached '{team_name}'!")
            success_count += 1
        except Exception as e:
            print(f"    [Error] Failed to import '{team_name}': {e}")
            traceback.print_exc()
            failed_count += 1
        
        # Polite delay to respect API rate limits
        import time
        time.sleep(2.0)
            
    print("\n========================================")
    print("World Cup Import Summary:")
    print(f"  - Successfully imported: {success_count}")
    print(f"  - Skipped (already in cache): {skipped_count}")
    print(f"  - Failed to import: {failed_count}")
    print(f"  - Total teams in cache now: {len(load_cache())}")
    print("========================================")

if __name__ == "__main__":
    main()
