import os
import json
import re
import requests
import time
import urllib.parse
import unicodedata

# Copied for testing
NAME_EXPANSIONS = {
    # Manchester City
    "K. Walker": "Kyle Walker",
    "R. Dias": "Rúben Dias",
    "M. Akanji": "Manuel Akanji",
    "J. Gvardiol": "Joško Gvardiol",
    "J. Stones": "John Stones",
    "B. Silva": "Bernardo Silva",
    "K. De Bruyne": "Kevin De Bruyne",
    "P. Foden": "Phil Foden",
    "E. Haaland": "Erling Haaland",
    # Real Madrid
    "A. Lunin": "Andriy Lunin",
    "D. Carvajal": "Dani Carvajal",
    "A. Rüdiger": "Antonio Rüdiger",
    "F. Mendy": "Ferland Mendy",
    "F. Valverde": "Federico Valverde",
    "T. Kroos": "Toni Kroos",
    "E. Camavinga": "Eduardo Camavinga",
    "J. Bellingham": "Jude Bellingham",
    "Vinícius Jr.": "Vinícius Júnior",
    # Bayern
    "M. Neuer": "Manuel Neuer",
    "J. Kimmich": "Joshua Kimmich",
    "M. de Ligt": "Matthijs de Ligt",
    "E. Dier": "Eric Dier",
    "N. Mazraoui": "Noussair Mazraoui",
    "K. Laimer": "Konrad Laimer",
    "A. Pavlović": "Aleksandar Pavlović",
    "L. Sané": "Leroy Sané",
    "T. Müller": "Thomas Müller",
    "J. Musiala": "Jamal Musiala",
    "H. Kane": "Harry Kane",
    # Arsenal
    "D. Raya": "David Raya",
    "B. White": "Ben White",
    "W. Saliba": "William Saliba",
    "G. Magalhães": "Gabriel Magalhães",
    "J. Kiwior": "Jakub Kiwior",
    "D. Rice": "Declan Rice",
    "M. Ødegaard": "Martin Ødegaard",
    "B. Saka": "Bukayo Saka",
    "G. Martinelli": "Gabriel Martinelli",
    "K. Havertz": "Kai Havertz",
    # Haiti
    "L. Joseph": "Leonel Joseph",
    "R. Providence": "Ruben Providence",
    "F. Pierrot": "Frantzdy Pierrot",
    # Spain
    "U. Simón": "Unai Simón",
    "M. Llorente": "Marcos Llorente",
    "P. Cubarsí": "Pau Cubarsí",
    "A. Laporte": "Aymeric Laporte",
    "M. Cucurella": "Marc Cucurella",
    "A. Baena": "Alex Baena",
    "F. Ruiz": "Fabian Ruiz",
    "F. Torres": "Ferran Torres",
    "M. Oyarzabal": "Mikel Oyarzabal",
    # Peru
    "P. Gallese": "Pedro Gallese",
    "R. Garces": "Renzo Garcés",
    "F. Gruber": "Franz Gruber",
    "O. Sonne": "Oliver Sonne",
    "J. Pretell": "Jesús Pretell",
    "E. Noriega": "Erick Noriega",
    "J. Vélez": "Jairo Vélez",
    "Y. Yotún": "Yoshimar Yotún",
    "M. López": "Marcos López",
    "A. Ugarriza": "Adrián Ugarriza",
    # Liverpool
    "Alisson B.": "Alisson Becker",
    "I. Konaté": "Ibrahima Konaté",
    "V. van Dijk": "Virgil van Dijk",
    "A. Robertson": "Andrew Robertson",
    "W. Endo": "Wataru Endo",
    "L. Díaz": "Luis Díaz",
    "D. Núñez": "Darwin Núñez",
    # Philippines
    "N. Etheridge": "Neil Etheridge",
    "C. de Murga": "Carli de Murga",
    "A. Aguinaldo": "Amani Aguinaldo",
    "C. Rontini": "Christian Rontini",
    "D. Sato": "Daisuke Sato",
    "K. Ingreso": "Kevin Ingreso",
    "S. Schröck": "Stephan Schröck",
    "P. Reichelt": "Patrick Reichelt",
    # Guam
    "D. Jaye": "Dallas Jaye",
    "T. Nicklaw": "Travis Nicklaw",
    "M. Grimes": "Marcus Grimes",
    "J. Grindeland": "Joey Grindeland",
    "M. Chargualaf": "Mark Chargualaf",
    "I. Mariano": "Ian Mariano",
    "M. Lopez": "Marcus Lopez",
    "J. Cunliffe": "Jason Cunliffe",
    "S. Spindel": "Shawn Spindel",
    "S. Malcolm": "Shane Malcolm",
    # Japan
    "Z. Suzuki": "Zion Suzuki",
    "Y. Sugawara": "Yukinari Sugawara",
    "K. Itakura": "Ko Itakura",
    "K. Machida": "Koki Machida",
    "H. Ito": "Hiroki Ito",
    "H. Morita": "Hidemasa Morita",
    "R. Doan": "Ritsu Doan",
    "T. Minamino": "Takumi Minamino",
    "K. Mitoma": "Kaoru Mitoma",
    "A. Ueda": "Ayase Ueda",
    # Portugal
    "C. Ronaldo": "Cristiano Ronaldo",
    # Argentina
    "G. Rulli": "Gerónimo Rulli",
    "F. Medina": "Facundo Medina",
    "L. Martínez": "Lisandro Martínez",
    "N. Otamendi": "Nicolás Otamendi",
    "A. Giay": "Agustín Giay",
    "V. Barco": "Valentín Barco",
    "E. Palacios": "Exequiel Palacios",
    "G. Lo Celso": "Giovani Lo Celso",
    "G. Simeone": "Giuliano Simeone",
    "J. López": "José Manuel López",
    "N. Paz": "Nico Paz",
    # Iceland
    "E. Ólafsson": "Elías Rafn Ólafsson",
    "L. Tómasson": "Logi Tómasson",
    "H. Magnússon": "Hörður Björgvin Magnússon",
    "D. Grétarsson": "Daníel Leó Grétarsson",
    "V. Pálsson": "Victor Pálsson",
    "M. Ellertsson": "Mikael Egill Ellertsson",
    "Í. B. Jóhannesson": "Ísak Bergmann Jóhannesson",
    "A. Baldursson": "Andri Baldursson",
    "A. Guðmundsson": "Albert Guðmundsson",
    "H. Haraldsson": "Hákon Arnar Haraldsson",
    "O. S. Óskarsson": "Orri Óskarsson",
}

PREDEFINED_ROSTERS_KEYS = [
    "manchester city", "real madrid", "bayern", "arsenal", "haiti", "new zealand", 
    "spain", "peru", "liverpool", "philippines", "guam", "japan", "portugal", "argentina", "iceland"
]

def clean_text(text: str) -> str:
    """Removes accents, lowercases, and strips non-alphanumeric chars for matching."""
    text_unicode = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text_clean = re.sub(r'[^a-zA-Z0-9\s]', '', text_unicode).lower().strip()
    return re.sub(r'\s+', ' ', text_clean)

def resolve_fotmob_id(player_name: str, team_name: str = "") -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    
    # Expand name
    search_name = NAME_EXPANSIONS.get(player_name, player_name)
    url = f"https://apigw.fotmob.com/searchapi/suggest?term={urllib.parse.quote_plus(search_name)}&lang=en"
    
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            # We look in squadMemberSuggest (or any suggest list)
            options = []
            for val in data.values():
                if isinstance(val, list):
                    for group in val:
                        if isinstance(group, dict) and "options" in group:
                            options.extend(group["options"])
            
            if not options:
                return ""
            
            # Clean search name for matching
            target_clean = clean_text(search_name)
            
            # Match scoring logic
            best_opt = None
            best_match_level = 0 # 0=none, 1=partial name match, 2=exact name match, 3=exact name + team match
            
            for opt in options:
                payload = opt.get("payload", {})
                pid = payload.get("id")
                if not pid:
                    continue
                    
                opt_name = opt.get("text", "").split("|")[0]
                opt_name_clean = clean_text(opt_name)
                opt_team = payload.get("teamName", "")
                
                # Check match level
                match_level = 0
                if opt_name_clean == target_clean:
                    match_level = 2
                    # If team also matches
                    if team_name and clean_text(team_name) in clean_text(opt_team):
                        match_level = 3
                elif target_clean in opt_name_clean or opt_name_clean in target_clean:
                    match_level = 1
                
                if match_level > best_match_level:
                    best_match_level = match_level
                    best_opt = opt
                elif match_level == best_match_level and best_opt:
                    # If match level is equal, prefer higher score
                    if opt.get("score", 0) > best_opt.get("score", 0):
                        best_opt = opt
            
            # Fallback if no clean matches, just take the first option if it is somewhat relevant
            if not best_opt and options:
                best_opt = options[0]
                
            if best_opt:
                return best_opt.get("payload", {}).get("id", "")
    except Exception as e:
        print(f"Error resolving {player_name}: {e}")
    return ""

def test_all_rosters():
    # Load roster_store to get rosters
    # Since we can just import backend.roster_store
    from backend.roster_store import PREDEFINED_ROSTERS
    
    total = 0
    resolved = 0
    
    for team, players in PREDEFINED_ROSTERS.items():
        print(f"\n===== Team: {team.upper()} =====")
        for p in players:
            name = p["name"]
            sofa_id = p.get("sofa_id", "")
            sub = p.get("sub", False)
            total += 1
            
            # Resolve FotMob ID
            # Let's sleep a little bit (0.1s) to avoid spamming
            time.sleep(0.1)
            fotmob_id = resolve_fotmob_id(name, team)
            
            if fotmob_id:
                resolved += 1
                print(f"  {name} (Sub: {sub}) -> FotMob ID: {fotmob_id} | Sofa ID: {sofa_id}")
            else:
                print(f"  FAILED to resolve {name} (Sub: {sub})")
                
    print(f"\nResolution rate: {resolved}/{total} ({resolved/total*100:.1f}%)")

if __name__ == "__main__":
    test_all_rosters()
