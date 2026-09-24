import hashlib
import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List, Tuple
from langchain_core.documents import Document
from backend.loaders.cleaner import clean_text
from backend.utils import logger

# Pages ingested from a URL are saved to data/raw as text files whose first line
# records where they came from, so a full re-index keeps them (with the URL as
# their citation) instead of silently dropping them.
URL_HEADER = "Source URL: "


def url_document_path(raw_dir: Path, url: str) -> Path:
    """Stable data/raw filename for a URL's saved text."""
    slug = re.sub(r"^https?://(www\.)?", "", url.strip().lower())
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")[:60]
    digest = hashlib.sha1(url.strip().encode("utf-8")).hexdigest()[:8]
    return raw_dir / f"web_{slug}_{digest}.txt"


def save_url_document(raw_dir: Path, url: str, docs: List[Document]) -> Tuple[Path, bool]:
    """Writes a scraped page to data/raw. Returns (path, already_existed)."""
    path = url_document_path(raw_dir, url)
    existed = path.exists()
    raw_dir.mkdir(parents=True, exist_ok=True)
    body = "\n\n".join(d.page_content for d in docs)
    path.write_text(f"{URL_HEADER}{url.strip()}\n{body}", encoding="utf-8")
    return path, existed

def load_blog(file_path: Path) -> List[Document]:
    """
    Loads text from a local blog file (HTML, text, or markdown), cleaning contents.
    
    If HTML, strips navigation, styling, scripts, and footers, and returns 
    the core readable content as a LangChain Document.
    """
    documents = []
    suffix = file_path.suffix.lower()
    
    try:
        if suffix in [".html", ".htm"]:
            logger.info(f"Loading HTML blog: {file_path.name}")
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                html_content = f.read()
                
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Decompose boilerplate elements
            for element in soup(["script", "style", "nav", "header", "footer", "aside", "form", "iframe"]):
                element.decompose()
                
            # Attempt to retrieve main container first
            main_content = soup.find("article") or soup.find("main") or soup.find("div", {"class": re.compile(r"content|post|article|body")})
            
            if main_content:
                text = main_content.get_text(separator="\n")
            else:
                text = soup.get_text(separator="\n")
                
            cleaned = clean_text(text)
            if cleaned.strip():
                doc = Document(
                    page_content=cleaned,
                    metadata={
                        "source": file_path.name,
                        "type": "blog"
                    }
                )
                documents.append(doc)
                
        elif suffix in [".txt", ".md"]:
            logger.info(f"Loading plain text/markdown blog: {file_path.name}")
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()
                
            metadata = {"source": file_path.name, "type": "text"}
            first_line, _, rest = raw_text.partition("\n")
            if first_line.startswith(URL_HEADER):
                metadata = {"source": first_line[len(URL_HEADER):].strip(), "type": "blog_url"}
                raw_text = rest

            cleaned = clean_text(raw_text)
            if cleaned.strip():
                doc = Document(page_content=cleaned, metadata=metadata)
                documents.append(doc)
        else:
            logger.warning(f"Unsupported file format for blog_loader: {suffix}")
            
    except Exception as e:
        logger.error(f"Error loading blog {file_path.name}: {str(e)}")
        
    return documents

def load_blog_from_url(url: str) -> List[Document]:
    """
    Scrapes and processes a blog post from a remote URL.
    """
    documents = []
    try:
        logger.info(f"Fetching remote blog URL: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Decompose boilerplate elements
        for element in soup(["script", "style", "nav", "header", "footer", "aside", "form", "iframe"]):
            element.decompose()
            
        main_content = soup.find("article") or soup.find("main")
        if main_content:
            text = main_content.get_text(separator="\n")
        else:
            text = soup.get_text(separator="\n")
            
        cleaned = clean_text(text)
        if cleaned.strip():
            doc = Document(
                page_content=cleaned,
                metadata={
                    "source": url,
                    "type": "blog_url"
                }
            )
            documents.append(doc)
            logger.info(f"Successfully fetched and parsed blog from: {url}")
    except Exception as e:
        logger.error(f"Error scraping blog from URL {url}: {str(e)}")
        
    return documents
