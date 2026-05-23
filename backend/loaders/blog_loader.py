import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List
from langchain_core.documents import Document
from backend.loaders.cleaner import clean_text
from backend.utils import logger

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
                
            cleaned = clean_text(raw_text)
            if cleaned.strip():
                doc = Document(
                    page_content=cleaned,
                    metadata={
                        "source": file_path.name,
                        "type": "text"
                    }
                )
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
