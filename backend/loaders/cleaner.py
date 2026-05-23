import re

def clean_text(text: str) -> str:
    """
    Standardizes and cleans text to improve embeddings and LLM analysis quality.
    
    Includes standardizing spaces, repairing broken hyphens across line breaks,
    filtering unwanted non-printable characters, and removing redundant linebreaks.
    """
    if not text:
        return ""

    # Replace zero-width spaces and other odd unicode characters
    text = text.replace("\u200b", "").replace("\u200c", "").replace("\ufeff", "")
    
    # Repair hyphens split across lines (e.g., "half-\nspace" -> "half-space")
    text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1-\2", text)
    
    # Standardize curly quotes and apostrophes to standard straight ones
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    
    # Replace multiple vertical spacing/newlines with a single standard double-newline (paragraph break)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    
    # Standardize tabs and vertical spaces to a single space
    text = re.sub(r"[ \t]+", " ", text)
    
    # Strip leading/trailing whitespaces from each individual line
    lines = [line.strip() for line in text.split("\n")]
    
    # Reassemble and strip overall margins
    cleaned_text = "\n".join(lines).strip()
    
    return cleaned_text
