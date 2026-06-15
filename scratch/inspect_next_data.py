import json

def inspect_json():
    with open("scratch/next_data.json", "r") as f:
        data = json.load(f)
        
    # Search recursively for keys or values containing match or lineup info
    print("Searching NextData...")
    
    def search_dict(d, path=""):
        if isinstance(d, dict):
            for k, v in d.items():
                new_path = f"{path}.{k}" if path else k
                if "lineup" in k.lower() or "lineup" in str(v).lower():
                    print(f"Found lineup keyword in key/val at path: {new_path}")
                if "scotland" in k.lower() or "scotland" in str(v).lower():
                    print(f"Found scotland keyword at path: {new_path}")
                search_dict(v, new_path)
        elif isinstance(d, list):
            for i, item in enumerate(d):
                new_path = f"{path}[{i}]"
                search_dict(item, new_path)
                
    search_dict(data)

if __name__ == "__main__":
    inspect_json()
