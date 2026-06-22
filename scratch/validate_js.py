import re

def validate():
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Extract the script block
    scripts = re.findall(r'<script>(.*?)</script>', content, re.DOTALL)
    print(f"Found {len(scripts)} script blocks.")
    
    # Let's write the javascript to a temp file and try parsing it if possible
    # Or count the number of opening and closing curly braces to check matching
    for i, script in enumerate(scripts):
        open_braces = script.count('{')
        close_braces = script.count('}')
        open_parens = script.count('(')
        close_parens = script.count(')')
        print(f"Script {i}: open braces={open_braces}, close braces={close_braces}")
        print(f"Script {i}: open parens={open_parens}, close parens={close_parens}")
        
        # Let's save it to a temp js file
        temp_js = f"scratch/temp_script_{i}.js"
        with open(temp_js, "w", encoding="utf-8") as js_f:
            js_f.write(script)
        print(f"Saved script to {temp_js}")

if __name__ == "__main__":
    validate()
