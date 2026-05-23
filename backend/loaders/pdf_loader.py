import pypdf
from pathlib import Path
from typing import List
from langchain_core.documents import Document
from backend.loaders.cleaner import clean_text
from backend.utils import logger

def load_pdf(file_path: Path) -> List[Document]:
    """
    Loads text from a PDF file page by page, applying cleaning procedures.
    
    Each page is returned as a LangChain Document with source and page metadata.
    """
    documents = []
    try:
        reader = pypdf.PdfReader(file_path)
        num_pages = len(reader.pages)
        logger.info(f"Loading PDF: {file_path.name} ({num_pages} pages)")
        
        for page_idx, page in enumerate(reader.pages):
            page_num = page_idx + 1
            raw_text = page.extract_text() or ""
            cleaned = clean_text(raw_text)
            
            # Skip empty pages
            if not cleaned.strip():
                continue
                
            doc = Document(
                page_content=cleaned,
                metadata={
                    "source": file_path.name,
                    "page": page_num,
                    "type": "pdf"
                }
            )
            documents.append(doc)
            
        logger.info(f"Loaded {len(documents)} pages from {file_path.name}")
    except Exception as e:
        logger.error(f"Error loading PDF {file_path.name}: {str(e)}")
        
    return documents
