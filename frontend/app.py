import streamlit as st
import requests
import os
from typing import Dict, Any, List

# Define Backend URL (load from env or fall back to localhost)
BACKEND_URL = os.getenv("FOOTBOT_BACKEND_URL", "http://127.0.0.1:8000")

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="FootBot | Elite Tactical Football Analysis",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Premium Custom Styling (Aesthetics) ---
st.markdown("""
<style>
    /* Premium fonts and custom colors */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Space+Grotesk:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .stApp {
        background: linear-gradient(135deg, #0e1612 0%, #070908 100%);
    }
    
    /* Header gradients */
    .title-gradient {
        background: linear-gradient(90deg, #10b981 0%, #059669 50%, #34d399 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 800;
        font-size: 3rem !important;
        margin-bottom: 0.2rem;
        letter-spacing: -0.05rem;
    }
    
    .subtitle-text {
        font-size: 1.1rem;
        color: #9ca3af;
        margin-bottom: 2rem;
        font-weight: 300;
    }
    
    /* Custom Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #0b110e !important;
        border-right: 1px solid #1f2937;
    }
    
    /* Cards and badges */
    .metric-card {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 0.75rem;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .badge {
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
    }
    
    .badge-online { background-color: rgba(16, 185, 129, 0.15); color: #10b981; border: 1.5px solid #10b981; }
    .badge-offline { background-color: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1.5px solid #ef4444; }
    .badge-warning { background-color: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1.5px solid #f59e0b; }
    .badge-info { background-color: rgba(59, 130, 246, 0.15); color: #3b82f6; border: 1.5px solid #3b82f6; }
    
    /* Chat bubbles */
    .user-chat-bubble {
        background-color: #1f2937;
        border-radius: 1rem 1rem 0 1rem;
        padding: 1rem;
        color: #f3f4f6;
        margin-bottom: 0.5rem;
    }
    
    .bot-chat-bubble {
        background-color: #0f2a1d;
        border: 1px solid #10b981;
        border-radius: 1rem 1rem 1rem 0;
        padding: 1rem;
        color: #f3f4f6;
        margin-bottom: 0.5rem;
    }
    
    /* Source details */
    .source-container {
        background-color: #0a0f0d;
        border-left: 3px solid #10b981;
        padding: 0.75rem;
        margin-top: 0.5rem;
        margin-bottom: 0.5rem;
        border-radius: 0 0.5rem 0.5rem 0;
    }
    
    /* Micro animations */
    .hover-effect:hover {
        transform: translateY(-2px);
        transition: transform 0.2s ease-in-out;
    }
</style>
""", unsafe_allow_html=True)

# --- Backend API Interaction Helpers ---

def get_backend_health() -> Dict[str, Any]:
    """Queries backend health check endpoint."""
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=3)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return {"status": "offline", "vector_db_loaded": False, "openai_initialized": False, "openai_model": ""}

def submit_query_to_backend(query: str, top_k: int, temp: float, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Posts user query to backend server."""
    try:
        payload = {
            "query": query,
            "top_k": top_k,
            "temperature": temp,
            "session_id": session_id
        }
        response = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=60)
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "response": f"⚠️ **Backend Error ({response.status_code})**: {response.text}",
                "is_rag_active": False,
                "is_mock": False,
                "sources": []
            }
    except Exception as e:
        return {
            "response": f"🚨 **Network Connection Error**: Unable to contact FootBot FastAPI backend at `{BACKEND_URL}`.\n\n*Details: {str(e)}*\n\nEnsure that the backend server is running: `uvicorn backend.main:app --reload`.",
            "is_rag_active": False,
            "is_mock": False,
            "sources": []
        }

def trigger_backend_ingestion() -> Dict[str, Any]:
    """Posts dynamic re-indexing signal to backend."""
    try:
        response = requests.post(f"{BACKEND_URL}/ingest", timeout=120)
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "error", "message": f"Server error: {response.text}"}
    except Exception as e:
        return {"status": "error", "message": f"Connection error: {str(e)}"}

def get_live_matches_feed() -> Dict[str, Any]:
    """Queries backend live matches feed."""
    try:
        response = requests.get(f"{BACKEND_URL}/live-matches", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return {"status": "error", "count": 0, "feed": []}

# --- App Header Layout ---
col_logo, col_desc = st.columns([1, 8])
with col_logo:
    st.markdown("<h1 style='font-size: 3.5rem; text-align: center; margin-top: 0.5rem;'>⚽</h1>", unsafe_allow_html=True)
with col_desc:
    st.markdown("<div class='title-gradient'>FootBot</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle-text'>Intelligent RAG Platform for Elite Football Tactics, Philosophy, and Player Analysis</div>", unsafe_allow_html=True)

# --- Sidebar Control Panel ---
st.sidebar.markdown("<h2 style='color:#10b981; font-family:\"Space Grotesk\";'>🧠 CONTROL CENTER</h2>", unsafe_allow_html=True)

# 1. System Health Check Badges
health = get_backend_health()
st.sidebar.markdown("<h4 style='margin-bottom:0.5rem;'>System Health Status</h4>", unsafe_allow_html=True)

# Build status widgets
if health["status"] == "healthy":
    st.sidebar.markdown("<span class='badge badge-online'>🟢 FastAPI Online</span>", unsafe_allow_html=True)
    
    if health["vector_db_loaded"]:
        st.sidebar.markdown("<span class='badge badge-online'>🟢 FAISS DB Active</span>", unsafe_allow_html=True)
    else:
        st.sidebar.markdown("<span class='badge badge-warning'>🟡 FAISS DB Empty</span>", unsafe_allow_html=True)
        
    if health["openai_initialized"]:
        st.sidebar.markdown(f"<span class='badge badge-online'>🟢 OpenAI Active ({health['openai_model']})</span>", unsafe_allow_html=True)
    else:
        st.sidebar.markdown("<span class='badge badge-warning'>🟡 OpenAI Offline (Demo Mode)</span>", unsafe_allow_html=True)
else:
    st.sidebar.markdown("<span class='badge badge-offline'>🔴 FastAPI Offline</span>", unsafe_allow_html=True)
    st.sidebar.markdown("<span class='badge badge-offline'>🔴 FAISS DB Offline</span>", unsafe_allow_html=True)
    st.sidebar.markdown("<span class='badge badge-warning'>🟡 Running in Standalone Demo Mode</span>", unsafe_allow_html=True)

st.sidebar.markdown("---")

# 2. Sliders and parameters configurations
st.sidebar.markdown("<h4>Hyperparameter Tuning</h4>", unsafe_allow_html=True)
top_k = st.sidebar.slider(
    "Retrieval Top-K Chunks", 
    min_value=1, 
    max_value=8, 
    value=4, 
    help="How many matching document snippets to feed the tactical analyst."
)
temperature = st.sidebar.slider(
    "Creativity / Temperature", 
    min_value=0.0, 
    max_value=1.0, 
    value=0.7, 
    step=0.05,
    help="Higher values generate more creative tactical analogies; lower values remain strictly direct."
)

st.sidebar.markdown("---")

# 3. Document Ingestion Controller
st.sidebar.markdown("<h4>Tactical Repository Ingestion</h4>", unsafe_allow_html=True)
st.sidebar.info("Add tactical PDFs, match reports, or html blogs inside `/data/raw` then run Re-Index.")

if st.sidebar.button("⚡ Re-Index Raw Documents", use_container_width=True):
    with st.sidebar.spinner("Scanning, chunking, and compiling embeddings (FAISS)..."):
        ingest_res = trigger_backend_ingestion()
        
    if ingest_res["status"] == "success":
        st.sidebar.success(
            f"Index Built!\n"
            f"Files processed: {ingest_res.get('total_files_processed')}\n"
            f"Chunks compiled: {ingest_res.get('total_chunks_indexed')}"
        )
        st.rerun()
    else:
        st.sidebar.error(f"Ingestion failed: {ingest_res.get('message')}")

st.sidebar.markdown("---")
st.sidebar.markdown("<h4>🌐 Dynamic URL Scraper</h4>", unsafe_allow_html=True)
url_input = st.sidebar.text_input("Paste Tactical URL (HTML/Blog):", placeholder="https://example.com/blog")
if st.sidebar.button("🕸️ Scrape & Index URL", use_container_width=True):
    if url_input.strip():
        with st.sidebar.spinner("Fetching, cleaning, and indexing remote URL..."):
            try:
                res = requests.post(f"{BACKEND_URL}/ingest/url", json={"url": url_input.strip()}, timeout=120)
                if res.status_code == 200:
                    data = res.json()
                    st.sidebar.success(f"Success! Indexed {data.get('total_chunks_indexed')} chunks from URL!")
                    st.rerun()
                else:
                    st.sidebar.error(f"Error: {res.json().get('detail', 'Failed to parse URL')}")
            except Exception as e:
                st.sidebar.error(f"Failed to connect: {str(e)}")
    else:
        st.sidebar.warning("Please paste a valid URL first.")

# 4. Session History Sidebar deck
st.sidebar.markdown("---")
st.sidebar.markdown("<h4 style='color:#10b981; font-family:\"Space Grotesk\"; margin-bottom:0.5rem;'>📜 TACTICAL HISTORICAL LOGS</h4>", unsafe_allow_html=True)

# Add a New Session Button
if st.sidebar.button("➕ Start New Tactical Session", use_container_width=True):
    st.session_state.active_session_id = None
    st.session_state.messages = []
    st.rerun()

# Fetch and display saved sessions
try:
    sessions_res = requests.get(f"{BACKEND_URL}/sessions", timeout=3)
    if sessions_res.status_code == 200:
        saved_sessions = sessions_res.json()
        if saved_sessions:
            for s in saved_sessions:
                # Highlight active session
                is_active = st.session_state.get("active_session_id") == s["id"]
                label = f"💬 {s['title']}"
                if is_active:
                    label = f"➡️ 💬 {s['title']} (Active)"
                
                if st.sidebar.button(label, key=f"sess_{s['id']}", use_container_width=True):
                    st.session_state.active_session_id = s["id"]
                    # Fetch messages for this session
                    msg_res = requests.get(f"{BACKEND_URL}/sessions/{s['id']}/messages", timeout=5)
                    if msg_res.status_code == 200:
                        st.session_state.messages = []
                        for msg in msg_res.json():
                            st.session_state.messages.append({
                                "role": msg["role"],
                                "content": msg["content"],
                                "sources": msg["sources"],
                                "is_web_search_active": any(x.get("type") == "web_search" for x in msg["sources"]),
                                "is_live_matches_active": any(x.get("type") == "live_scores" or "REAL-TIME FOOTBALL LATEST SCORES" in x.get("text", "") for x in msg["sources"])
                            })
                        st.rerun()
        else:
            st.sidebar.caption("No historical sessions found.")
except Exception as e:
    st.sidebar.caption("Failed to load historical sessions.")

# Check if there is an active conversation to export as a formatted Dossier
if st.session_state.get("messages"):
    st.sidebar.markdown("---")
    st.sidebar.markdown("<h4 style='color:#10b981; font-family:\"Space Grotesk\"; margin-bottom:0.5rem;'>💾 EXPORT RESEARCH DOSSIER</h4>", unsafe_allow_html=True)
    
    # Compile markdown dossier
    dossier_text = [
        "# ⚽ FOOTBOT TACTICAL DOSSIER BRIEFING",
        "Generated by FootBot Premium Tactical AI Analyst Agent",
        f"Session ID: `{st.session_state.get('active_session_id', 'N/A')}`",
        "---",
        ""
    ]
    
    for idx, msg in enumerate(st.session_state.messages):
        role = "COACH / ANALYST" if msg["role"] == "user" else "FOOTBOT TACTICAL AGENT"
        dossier_text.append(f"### 👤 {role}")
        dossier_text.append(msg["content"])
        dossier_text.append("")
        
        # Format citations if present
        if msg.get("sources"):
            dossier_text.append("**Grounding Evidence & Citations:**")
            for src in msg["sources"]:
                if src.get("type") == "web_search":
                    dossier_text.append(f"- **Source [{src['index']}] (Web)**: [{src['source']}]({src['source']})")
                else:
                    dossier_text.append(f"- **Source [{src['index']}] (Tactics PDF/Blog)**: `{src['source']}` (Page: {src['page'] or 'N/A'}, Similarity Score: {src.get('score', 0):.3f})")
            dossier_text.append("")
        dossier_text.append("---")
        
    compiled_dossier = "\n".join(dossier_text)
    
    st.sidebar.download_button(
        label="💾 Export Active Tactical Dossier",
        data=compiled_dossier,
        file_name=f"footbot_tactical_dossier_{str(st.session_state.get('active_session_id', 'session'))[:8]}.md",
        mime="text/markdown",
        use_container_width=True,
        help="Downloads the complete tactical analysis thread as a beautifully formatted Markdown briefing document."
    )

st.sidebar.markdown("---")
st.sidebar.markdown("<div style='font-size:0.8rem; color:#6b7280; text-align:center;'>FootBot v1.0.0 • Akilan Flagship AI</div>", unsafe_allow_html=True)

# --- Main App Session State initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = None

# --- Main Application Tabs Layout ---
tab_chat, tab_live = st.tabs(["💬 Tactical AI Chat", "⚽ Live Match Ticker"])

with tab_chat:
    # --- Quick Start / Preset Prompts Cards ---
    st.markdown("### 📋 Quick Start Tactical Prompts")
    col1, col2, col3 = st.columns(3)
    
    preset_1 = "Compare Rodri and Busquets in positional play and tactical awareness."
    preset_2 = "How does Pep Guardiola use inverted fullbacks to overload the midfield?"
    preset_3 = "Compare Jurgen Klopp's gegenpressing traps and Mikel Arteta's high press triggers."
    
    with col1:
        if st.button(f"⚽ Pivot Evolution\n\n*Busquets vs Rodri*", use_container_width=True, key="preset1"):
            st.session_state.clicked_preset = preset_1
            
    with col2:
        if st.button(f"🏗️ Juego de Posición\n\n*Guardiola's Midfield Box*", use_container_width=True, key="preset2"):
            st.session_state.clicked_preset = preset_2
            
    with col3:
        if st.button(f"🛡️ Pressing Paradigms\n\n*Klopp vs Arteta*", use_container_width=True, key="preset3"):
            st.session_state.clicked_preset = preset_3
            
    st.markdown("---")
    
    # --- Chat Board Container ---
    
    # Render historical messages
    for msg in st.session_state.messages:
        role = msg["role"]
        avatar = "⚽" if role == "assistant" else "👤"
        
        with st.chat_message(role, avatar=avatar):
            # Render dynamic live web search badge if active
            if role == "assistant" and msg.get("is_web_search_active"):
                st.markdown("<span class='badge badge-info'>🌐 Live Web Search Fallback Active</span>", unsafe_allow_html=True)
            if role == "assistant" and msg.get("is_live_matches_active"):
                st.markdown("<span class='badge badge-online'>🟢 Live Scores & News Injected</span>", unsafe_allow_html=True)
                
            # Display response text
            st.markdown(msg["content"])
            
            # Display source expander if there are sources associated with the response
            if role == "assistant" and msg.get("sources"):
                with st.expander("🔍 Tactical Grounding Sources (RAG Evidence)"):
                    for src in msg["sources"]:
                        if src.get("type") == "web_search":
                            st.markdown(
                                f"**Source [{src['index']}]**: 🔗 [Web Link: {src['source']}]({src['source']}) "
                                f"(Relevance Score: `{src['score']:.3f}`)"
                            )
                        else:
                            st.markdown(
                                f"**Source [{src['index']}]**: `{src['source']}` "
                                f"(Page: `{src['page'] or 'N/A'}`, Relevance: `{src['score']:.3f}`)"
                            )
                        st.info(src["text"])
                        
    # Handle clickable presets
    query = None
    if "clicked_preset" in st.session_state and st.session_state.clicked_preset:
        query = st.session_state.clicked_preset
        st.session_state.clicked_preset = None # reset
        
    # Handle manual chat box inputs
    user_input = st.chat_input("Ask FootBot a tactical football question (e.g. Compare Rodri and Busquets)...")
    if user_input:
        query = user_input
        
    # --- RAG Orchestration Flow ---
    if query:
        # 1. Store user message in history and render it
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user", avatar="👤"):
            st.markdown(query)
            
        # 2. Query FastAPI server
        with st.chat_message("assistant", avatar="⚽"):
            response_placeholder = st.empty()
            spinner_placeholder = st.empty()
            
            with spinner_placeholder:
                st.markdown("*FootBot is consulting technical literature & generating tactical analysis...*")
                st.spinner()
                
            # Perform REST API request
            result = submit_query_to_backend(query, top_k, temperature, st.session_state.get("active_session_id"))
            
            # Remove spinner
            spinner_placeholder.empty()
            
            # Render dynamic web search badge if active
            if result.get("is_web_search_active"):
                st.markdown("<span class='badge badge-info'>🌐 Live Web Search Fallback Active</span>", unsafe_allow_html=True)
            if result.get("is_live_matches_active"):
                st.markdown("<span class='badge badge-online'>🟢 Live Scores & News Injected</span>", unsafe_allow_html=True)
                
            # Render markdown response
            response_text = result["response"]
            response_placeholder.markdown(response_text)
            
            # If sources exist, render expander and display them
            sources = result.get("sources", [])
            if sources:
                with st.expander("🔍 Tactical Grounding Sources (RAG Evidence)"):
                    for src in sources:
                        if src.get("type") == "web_search":
                            st.markdown(
                                f"**Source [{src['index']}]**: 🔗 [Web Link: {src['source']}]({src['source']}) "
                                f"(Relevance Score: `{src['score']:.3f}`)"
                            )
                        else:
                            st.markdown(
                                f"**Source [{src['index']}]**: `{src['source']}` "
                                f"(Page: `{src['page'] or 'N/A'}`, Relevance: `{src['score']:.3f}`)"
                            )
                        st.info(src["text"])
                        
        # 3. Store assistant message in history and record the session ID
        st.session_state.active_session_id = result.get("session_id")
        st.session_state.messages.append({
            "role": "assistant",
            "content": response_text,
            "sources": sources,
            "is_web_search_active": result.get("is_web_search_active", False),
            "is_live_matches_active": result.get("is_live_matches_active", False)
        })
        st.rerun()

with tab_live:
    st.markdown("<h3 style='color:#10b981; font-family:\"Space Grotesk\"; margin-top:0;'>⚽ Real-Time Football Scores & Headlines</h3>", unsafe_allow_html=True)
    st.markdown("Retrieving latest scores and breaking transfer updates live from public BBC Sport RSS feeds.")
    
    # Button to force reload feed
    if st.button("🔄 Refresh Live Match Scores", use_container_width=True):
        st.rerun()
        
    with st.spinner("Crawling live matches and news..."):
        feed_data = get_live_matches_feed()
        
    if feed_data.get("status") == "success" and feed_data.get("feed"):
        feed = feed_data.get("feed")
        matches = [f for f in feed if f.get("is_match")]
        news = [f for f in feed if not f.get("is_match")]
        
        # Extract unique list of leagues
        leagues = sorted(list(set([m.get("league", "Unknown League") for m in matches if m.get("league")])))
        
        st.markdown("<h4 style='color:#34d399; font-family:\"Space Grotesk\"; margin-top:1.5rem;'>🔍 Search & Filter Matchday</h4>", unsafe_allow_html=True)
        
        # Interactive Search & Filter Row - Two Columns Layout
        col_ctrl1, col_ctrl2 = st.columns(2)
        
        with col_ctrl1:
            search_query = st.text_input("🔍 Search Teams or Leagues:", placeholder="e.g. Miami, Rosenborg, or MLS")
            
        with col_ctrl2:
            filter_leagues = st.multiselect(
                "🏆 Filter by Leagues:",
                options=leagues,
                default=[],
                help="Select one or more leagues to display."
            )
            
        st.markdown("---")
        
        # Apply filters to Matches
        filtered_matches = []
        for m in matches:
            m_league = m.get("league", "").lower()
            m_title = m.get("title", "").lower()
            
            # 1. Multi-select League filter check
            if filter_leagues:
                if m.get("league") not in filter_leagues:
                    continue
            
            # 2. Text search query check
            if search_query:
                q = search_query.lower()
                if q not in m_title and q not in m_league:
                    continue
            
            filtered_matches.append(m)
            
        # Apply search query filter to News as well
        filtered_news = []
        for n in news:
            if search_query:
                q = search_query.lower()
                if q not in n.get("title", "").lower() and q not in n.get("description", "").lower():
                    continue
            filtered_news.append(n)
            
        # Render columns for matches and headlines
        col_m, col_n = st.columns([1, 1])
        
        with col_m:
            st.markdown(f"#### 🏆 Match Fixtures & Live Scores ({len(filtered_matches)})")
            if filtered_matches:
                for m in filtered_matches:
                    league_name = m.get("league", "Unknown League")
                    league_badge = f"<span class='badge badge-info' style='margin-bottom:0.4rem;'>🏆 {league_name}</span>"
                    
                    st.markdown(f"""
                    <div class='metric-card hover-effect'>
                        {league_badge}
                        <h4 style='color:#34d399; margin:0;'>⚽ {m['title']}</h4>
                        <p style='color:#9ca3af; font-size:0.9rem; margin-top:0.4rem; margin-bottom:0.6rem;'>{m['description']}</p>
                        <a href='{m['link']}' target='_blank' style='color:#10b981; font-size:0.85rem; text-decoration:none;'>🔗 Match Centre Updates</a>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No active live fixtures match your search criteria.")
                
        with col_n:
            st.markdown(f"#### 📰 Breaking Football Headlines ({len(filtered_news)})")
            if filtered_news:
                for n in filtered_news:
                    st.markdown(f"""
                    <div class='metric-card hover-effect'>
                        <h5 style='color:#f3f4f6; margin:0;'>📢 {n['title']}</h5>
                        <p style='color:#9ca3af; font-size:0.85rem; margin-top:0.4rem; margin-bottom:0.6rem;'>{n['description']}</p>
                        <p style='font-size:0.75rem; color:#6b7280; margin:0;'>Published: {n['published']}</p>
                        <a href='{n['link']}' target='_blank' style='color:#3b82f6; font-size:0.8rem; text-decoration:none;'>🔗 Read Full Report</a>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No football headlines match your search criteria.")
    else:
        st.error("Failed to retrieve live match scores. Ensure the backend server is online.")
