import os
import json
from pathlib import Path
from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

from backend.config import settings
from backend.utils import logger, ensure_directories
from backend.loaders.pdf_loader import load_pdf
from backend.loaders.blog_loader import load_blog

# Bootstrap Data Constants
SAMPLE_RODRI_BUSQUETS = """
Tactical Comparison: The Evolution of the Single Pivot - Sergio Busquets vs. Rodri
Author: FootBot Tactical Analysis Team

The single pivot position (the "number 6") is the structural heartbeat of any positional play (Juego de Posición) team. In this tactical essay, we analyze and contrast the profiles of two generation-defining Spanish pivots: Sergio Busquets, the anchor of Pep Guardiola’s legendary Barcelona side, and Rodri Hernandez, the engine of Manchester City’s treble-winning team.

1. Positional Discipline and Spatial Awareness:
Sergio Busquets operated primarily as a "stationary anchor." His intelligence lies in his spatial awareness and passive manipulation of opponents. Busquets rarely covers massive distances; instead, he positions himself perfectly to intercept passes, scan the pitch constantly (up to 3 times per second before receiving the ball), and act as a simple wall-pass option. His signature "La Pausa"—the ability to delay a pass to draw in defenders and open up lines behind them—is legendary.
Rodri, by contrast, is a highly dynamic, physical, and complete athlete. In Guardiola's modern 3-2-4-1 system, Rodri has to cover significantly more ground laterally and vertically. He acts as both a destroyer and a transition catalyst. Rodri is more aggressive in stepping up to press and has a powerful physical presence that allows him to dominate aerial duels and shield the ball under extreme physical duress.

2. Press Resistance and Ball Progression:
Under press, Busquets is a master of micro-movements. He uses shoulder drops, body orientation, and first-touch deflections to bypass opponents. His distribution is short, concise, and focused on finding the "third man" (often Xavi or Iniesta) to split lines.
Rodri is exceptionally press-resistant through sheer physical power and ball-shielding. His progression profile features high-volume, medium-to-long line-breaking passes. He often sweeps long cross-field diagonals to isolated wingers (like Jack Grealish or Bernardo Silva) to force defensive shifts. Rodri also possesses an elite long-range shooting threat (as seen in the 2023 Champions League Final), adding an offensive dimension Busquets rarely engaged in.

3. Defensive Cover and Rest Defense:
In defensive transitions (rest defense), Busquets relies on anticipatory geometry. Because Barcelona pressed high and compactly, Busquets’ role was to step forward, close down passing lanes, and execute tactical fouls or clean tackles before the counter-attack could accelerate.
Rodri operates in a more complex hybrid rest defense. He often partners with an inverting fullback (such as John Stones moving from center-back into midfield). This double-pivot structure allows Rodri more freedom to engage in physical ground duels while Stones secures the lateral spaces, making Man City exceptionally robust against vertical counters.
"""

SAMPLE_GUARDIOLA_PLAY = """
Pep Guardiola's Juego de Posición: Midfield Overloads and Inverted Fullbacks
Author: FootBot Tactical Analysis Team

Pep Guardiola's tactical philosophy centers on "Juego de Posición" (Positional Play). The fundamental tenet is the rational occupation of space, where the pitch is divided into a grid, and players adjust their positioning to ensure optimal passing lanes, superiorities, and numerical overloads.

1. The Rest Defense and Midfield Box (3-2-4-1):
In recent seasons, Guardiola revolutionized build-up play by migrating from a traditional 4-3-3 to an attacking 3-2-4-1. This is achieved by inverting a fullback or a center-back (e.g., John Stones, Manuel Akanji, or Rico Lewis) into the midfield pivot space alongside the primary holding midfielder (Rodri).
This inversion creates a compact "midfield box" or diamond (usually a 3-2-4-1 or 3-2-2-3 structure) consisting of three center-backs, a double pivot in midfield, two advanced "free eights" (like Kevin De Bruyne and Ilkay Gundogan) in the half-spaces, and two wide wingers hugging the touchline. This midfield box creates a natural numerical superiority (4v3 or 4v2) against opponent midfields, forcing defensive lines to make difficult decisions: do they step up to contest the double pivot, or do they drop deep to cover the interior playmakers?

2. Exploiting the Half-Spaces:
The half-space (the vertical zones between the flanks and the center) is the critical zone of creation. By positioning advanced playmakers in these half-spaces and pinning the opponent fullbacks wide via touchline-hugging wingers, Guardiola creates a "structural overload."
If an opponent fullback steps out to mark the wide winger, a gaping channel opens up in the half-space for the attacking midfielder to make a run into the box. If the opponent center-back slides across to cover the half-space run, it creates a 1v1 matchup in the center for the striker (Erling Haaland).

3. The Third Man Concept:
A core mechanism of Guardiola's ball progression is the "Third Man Run." Player A (the center-back) wants to pass to Player C (the advanced midfielder), but the passing lane is blocked by an opponent midfielder. Player A instead passes to Player B (the inverting pivot), who draws the opponent's attention and immediately plays a one-touch pass to Player C, who is facing forward and moving into open space. This third-man concept enables clean progression under heavy mid-block pressure.
"""

SAMPLE_KLOPP_ARTETA = """
Pressing Paradigms: Jurgen Klopp's Gegenpressing vs. Mikel Arteta's High Press
Author: FootBot Tactical Analysis Team

Squeezing the pitch and winning the ball high up is a core tenet of modern elite football. However, the mechanical execution of high-pressing structures varies significantly. In this tactical comparison, we analyze the structural and philosophical differences between Jurgen Klopp’s signature "Gegenpressing" and Mikel Arteta’s highly structured high press.

1. Jurgen Klopp's Gegenpressing (The German Counter-Press):
Klopp’s Gegenpressing is not just a defensive press; it is an offensive playmaker. The core philosophy is to press the opponent *immediately* (within 3-5 seconds) after losing possession. This is the moment when the opponent is most vulnerable because they have just started to transition into an offensive shape, opening up spaces.
Klopp’s counter-press is heavily ball-oriented and passing-lane oriented. The nearest players to the ball swarm the ball-carrier, cut off immediate short passing options, and force the opponent into hurried, long clearances or turnovers. Klopp utilizes "pressing traps"—intentionally leaving a lateral pass open, only to lock the receiver in a touchline cage with multiple pressing players.

2. Mikel Arteta's High Press (Man-Oriented Jump Triggers):
Mikel Arteta’s pressing philosophy, heavily influenced by Pep Guardiola and Marcelo Bielsa, is highly structured, spatial, and man-oriented. Rather than chaotic ball-oriented swarming, Arteta’s press relies on clear roles and "jump triggers."
In a typical 4-4-2 or 4-1-4-1 out-of-possession shape, the central striker initiates the press by cutting off the passing lane between the two opponent center-backs (curving their run). As the ball is played to a fullback, this is the "trigger" for the winger to jump aggressively, while the near-side attacking midfielder slides across to man-mark the opponent's pivot.
Arteta plays an extremely high defensive line with aggressive center-backs (like William Saliba and Gabriel Magalhães) who are instructed to step up and tight-mark opposing strikers, preventing them from turning or securing long-ball lay-offs. This squeezes the space, turning the midfield into a bottleneck.

3. Key Differences:
- Objective: Klopp presses to generate rapid, vertical counter-attacking opportunities (transitional chaos). Arteta presses to win the ball, regain structural control, and restart patient positional play.
- Structure: Gegenpressing is more reactive to the immediate loss of the ball and relies on intense horizontal narrowing around the ball. Arteta's high press is highly proactive, pre-organized based on opponent kick-offs/goalkeeper distributions, and focuses on strict man-to-man assignments in targeted zones.
"""

def bootstrap_sample_data():
    """Generates sample tactical files to ensure FootBot is immediately testable."""
    ensure_directories()
    raw_dir = settings.RAW_DATA_PATH
    
    samples = {
        "tactical_profile_rodri_vs_busquets.txt": SAMPLE_RODRI_BUSQUETS,
        "guardiola_positional_play_inverted_fullbacks.txt": SAMPLE_GUARDIOLA_PLAY,
        "klopp_gegenpressing_vs_arteta_high_press.txt": SAMPLE_KLOPP_ARTETA
    }
    
    bootstrapped_count = 0
    for filename, content in samples.items():
        filepath = raw_dir / filename
        if not filepath.exists():
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content.strip())
            logger.info(f"Bootstrapped sample document: {filename}")
            bootstrapped_count += 1
            
    return bootstrapped_count

def run_ingestion() -> dict:
    """
    Scans the raw data folder, extracts text, chunks it, embeds it, and indexes it in FAISS.
    
    Returns a dictionary summarizing the results (files loaded, chunks indexed, etc.).
    """
    logger.info("Initializing FootBot Document Ingestion Pipeline...")
    ensure_directories()
    
    # Auto-bootstrap if raw data folder is empty
    raw_files = list(settings.RAW_DATA_PATH.glob("*"))
    # Filter out hidden files like .DS_Store
    raw_files = [f for f in raw_files if not f.name.startswith(".")]
    
    if len(raw_files) == 0:
        logger.info("No raw documents found. Automatically bootstrapping sample data...")
        bootstrap_sample_data()
        raw_files = list(settings.RAW_DATA_PATH.glob("*"))
        raw_files = [f for f in raw_files if not f.name.startswith(".")]
        
    logger.info(f"Found {len(raw_files)} documents in raw folder for ingestion.")
    
    all_documents = []
    processed_metadata = []
    
    for file_path in raw_files:
        suffix = file_path.suffix.lower()
        docs = []
        if suffix == ".pdf":
            docs = load_pdf(file_path)
        elif suffix in [".html", ".htm", ".txt", ".md"]:
            docs = load_blog(file_path)
        else:
            logger.warning(f"Skipping unsupported file type: {file_path.name}")
            continue
            
        if docs:
            all_documents.extend(docs)
            processed_metadata.append({
                "filename": file_path.name,
                "file_size_bytes": file_path.stat().st_size,
                "extracted_pages_or_articles": len(docs),
                "status": "success"
            })
            
    if not all_documents:
        logger.warning("No documents successfully loaded. Vector database cannot be built.")
        return {
            "status": "error",
            "message": "No documents loaded. Ensure readable files are present in data/raw."
        }
        
    logger.info(f"Successfully loaded {len(all_documents)} raw document elements.")
    
    # Document splitting
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        length_function=len
    )
    chunks = text_splitter.split_documents(all_documents)
    logger.info(f"Split documents into {len(chunks)} overlapping chunks.")
    
    # Generate embeddings and FAISS index
    logger.info(f"Generating embeddings using model: {settings.EMBEDDING_MODEL_NAME}...")
    try:
        # Note: HuggingFaceEmbeddings downloads the model automatically to ~/.cache/huggingface
        embeddings = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL_NAME,
            model_kwargs={'device': 'cpu'}
        )
        
        logger.info("Indexing chunks in FAISS database...")
        db = FAISS.from_documents(chunks, embeddings)
        
        # Save vector database locally
        logger.info(f"Saving FAISS index locally to: {settings.FAISS_DB_PATH}")
        db.save_local(str(settings.FAISS_DB_PATH))
        
        # Save processed auditing metadata
        metadata_path = settings.PROCESSED_DATA_PATH / "ingestion_summary.json"
        summary_data = {
            "total_files_processed": len(raw_files),
            "total_chunks_indexed": len(chunks),
            "files": processed_metadata
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=4)
            
        logger.info("Document Ingestion and Indexing complete!")
        return {
            "status": "success",
            "total_files_processed": len(raw_files),
            "total_chunks_indexed": len(chunks),
            "summary_file": str(metadata_path)
        }
        
    except Exception as e:
        logger.error(f"Failed to generate embeddings or index FAISS: {str(e)}")
        return {
            "status": "error",
            "message": f"Embedding/FAISS compilation failure: {str(e)}"
        }

if __name__ == "__main__":
    # Allow execution directly from CLI
    result = run_ingestion()
    print(json.dumps(result, indent=2))
