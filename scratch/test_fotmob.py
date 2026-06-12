import requests
import urllib.parse
import unicodedata
import re

def remove_accents(input_str: str) -> str:
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def clean_special_chars(input_str: str) -> str:
    # Handle specific Icelandic characters
    s = input_str.replace('ð', 'd').replace('Ð', 'D')
    s = s.replace('þ', 'th').replace('Þ', 'Th')
    s = s.replace('æ', 'ae').replace('Æ', 'Ae')
    return remove_accents(s)

def test_custom_players():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    
    players = [
        ("E. Ólafsson", "Elías Rafn Ólafsson"),
        ("H. Magnússon", "Hörður Björgvin Magnússon"),
        ("D. Grétarsson", "Daníel Leó Grétarsson"),
        ("Dagur Dan Þórhallsson", "Dagur Dan Þórhallsson"),
        ("Jón Dagur Þorsteinsson", "Jón Dagur Þorsteinsson"),
        ("Kristall Máni Ingason", "Kristall Máni Ingason"),
        ("Manny Ott", "Manuel Ott"),
        ("OJ Porteria", "Jose Elmer Porteria")
    ]
    
    for orig, full in players:
        # Try full, then try cleaned full, then try cleaned original
        queries = [full, clean_special_chars(full), clean_special_chars(orig)]
        print(f"=== Player: {orig} / {full} ===")
        for q in queries:
            url = f"https://apigw.fotmob.com/searchapi/suggest?term={urllib.parse.quote_plus(q)}&lang=en"
            try:
                r = requests.get(url, headers=headers, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    options = []
                    for val in data.values():
                        if isinstance(val, list):
                            for group in val:
                                if isinstance(group, dict) and "options" in group:
                                    options.extend(group["options"])
                    
                    if options:
                        print(f"  Query '{q}' succeeded:")
                        for opt in options[:2]:
                            print(f"    Found: {opt.get('text')} -> ID: {opt.get('payload', {}).get('id')}")
                        break
                    else:
                        print(f"  Query '{q}' returned no options.")
                else:
                    print(f"  Query '{q}' failed with status {r.status_code}")
            except Exception as e:
                print(f"  Query '{q}' errored: {e}")

if __name__ == "__main__":
    test_custom_players()
