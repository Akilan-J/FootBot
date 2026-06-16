import re
import subprocess
import sys

def validate_js_in_html():
    html_path = "frontend/index.html"
    print(f"Reading {html_path}...")
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Extract all <script> contents
    scripts = re.findall(r'<script\b[^>]*>(.*?)</script>', content, re.DOTALL)
    if not scripts:
        print("No script tags found.")
        return
    
    for i, script_content in enumerate(scripts):
        temp_js_path = f"scratch/extracted_script_{i}.js"
        with open(temp_js_path, "w", encoding="utf-8") as temp_file:
            temp_file.write(script_content)
        
        print(f"Validating script {i} via node...")
        res = subprocess.run(["node", "--check", temp_js_path], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"🚨 SYNTAX ERROR in script {i}!")
            print(res.stderr)
            # Find the line number mapping
            # (Note: lines in temp file + offset of script tag in html)
            # Let's print the offending lines from the temp file
            err_lines = res.stderr.split('\n')
            for el in err_lines:
                if temp_js_path in el:
                    parts = el.split(':')
                    if len(parts) >= 2:
                        try:
                            line_num = int(parts[1])
                            print(f"Offending line {line_num} in extracted JS:")
                            js_lines = script_content.split('\n')
                            start = max(0, line_num - 5)
                            end = min(len(js_lines), line_num + 5)
                            for l_idx in range(start, end):
                                marker = "👉 " if l_idx == line_num - 1 else "   "
                                print(f"{marker}{l_idx+1}: {js_lines[l_idx]}")
                        except ValueError:
                            pass
            sys.exit(1)
        else:
            print(f"✅ Script {i} is syntactically valid.")

if __name__ == "__main__":
    validate_js_in_html()
