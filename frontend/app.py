import streamlit as st
import requests
import os
import re
from typing import Dict, Any, List, Optional

# Define Backend URL (load from env or fall back to localhost)
BACKEND_URL = os.getenv("FOOTBOT_BACKEND_URL", "http://127.0.0.1:8000")

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="FootBot | Elite Tactical Football Analysis",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Session State Initialization ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = True
if "token" not in st.session_state:
    st.session_state.token = "default_coach"
if "username" not in st.session_state:
    st.session_state.username = "Coach Akilan"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = None

# --- Premium Custom Styling (Aesthetics) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Space+Grotesk:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .stApp {
        background: linear-gradient(135deg, #090e0c 0%, #030504 100%);
    }
    
    /* Header gradients */
    .title-gradient {
        background: linear-gradient(90deg, #10b981 0%, #0d9488 50%, #34d399 100%);
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
        background-color: #050807 !important;
        border-right: 1px solid #1f2937;
    }
    
    /* Cards and badges */
    .metric-card {
        background-color: #0c1210;
        border: 1px solid #142820;
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
        margin-right: 0.4rem;
    }
    
    .badge-online { background-color: rgba(16, 185, 129, 0.1); color: #10b981; border: 1px solid #10b981; }
    .badge-offline { background-color: rgba(239, 68, 68, 0.1); color: #ef4444; border: 1px solid #ef4444; }
    .badge-warning { background-color: rgba(245, 158, 11, 0.1); color: #f59e0b; border: 1px solid #f59e0b; }
    .badge-info { background-color: rgba(59, 130, 246, 0.1); color: #3b82f6; border: 1px solid #3b82f6; }
    
    /* Pitch Visualizer styles */
    .pitch-container {
        background-color: #0b1e16;
        border: 2px solid #10b981;
        border-radius: 0.75rem;
        padding: 1rem;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    
    .pitch-ascii {
        font-family: 'Courier New', Courier, monospace;
        color: #34d399;
        font-size: 1rem;
        line-height: 1.2;
        white-space: pre-wrap;
        background-color: #050d09;
        padding: 1rem;
        border-radius: 0.5rem;
        display: inline-block;
        text-align: left;
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
        headers = {}
        if st.session_state.token:
            headers["X-User-Token"] = st.session_state.token
            
        response = requests.post(f"{BACKEND_URL}/chat", json=payload, headers=headers, timeout=60)
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
            "response": f"🚨 **Network Connection Error**: Unable to contact FootBot FastAPI backend at `{BACKEND_URL}`.\n\n*Details: {str(e)}*",
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
    """Queries backend live matches feed, filtering to include only men's matches."""
    try:
        response = requests.get(f"{BACKEND_URL}/live-matches", timeout=10)
        if response.status_code == 200:
            data = response.json()
            feed = data.get("feed", [])
            filtered_feed = []
            for m in feed:
                title = m.get("title", "").lower()
                league = m.get("league", "").lower()
                if "women" in title or "women" in league:
                    continue
                filtered_feed.append(m)
            data["feed"] = filtered_feed
            data["count"] = len(filtered_feed)
            return data
    except Exception:
        pass
    return {"status": "error", "count": 0, "feed": []}

def get_historical_matches_feed() -> List[Dict[str, Any]]:
    """Queries backend historical matches database, filtering to include only men's matches."""
    try:
        response = requests.get(f"{BACKEND_URL}/historical-matches", timeout=10)
        if response.status_code == 200:
            matches = response.json()
            filtered = []
            for m in matches:
                home = m.get("home_team", "").lower()
                away = m.get("away_team", "").lower()
                league = m.get("league", "").lower()
                if "women" in home or "women" in away or "women" in league:
                    continue
                filtered.append(m)
            return filtered
    except Exception:
        pass
    return []

def download_session_pdf(session_id: str) -> Optional[bytes]:
    """Downloads ReportLab tactical dossier PDF bytes from backend."""
    try:
        headers = {"X-User-Token": st.session_state.token}
        response = requests.get(f"{BACKEND_URL}/sessions/{session_id}/pdf", headers=headers, timeout=20)
        if response.status_code == 200:
            return response.content
    except Exception:
        pass
    return None

# --- App Header Layout ---
col_logo, col_desc = st.columns([1, 8])
with col_logo:
    st.markdown("<h1 style='font-size: 3.5rem; text-align: center; margin-top: 0.5rem;'>⚽</h1>", unsafe_allow_html=True)
with col_desc:
    st.markdown("<div class='title-gradient'>FootBot</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle-text'>Intelligent RAG Platform for Elite Football Tactics, Philosophy, and Player Analysis</div>", unsafe_allow_html=True)

# --- Sidebar Header and Control Panel ---
st.sidebar.markdown("<h3 style='color:#10b981; font-family:\"Space Grotesk\"; margin-bottom:0;'>👤 COACH PORTAL</h3>", unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.markdown("<h4 style='color:#10b981; font-family:\"Space Grotesk\"; margin-top:0;'>🧠 CONTROL CENTER</h4>", unsafe_allow_html=True)

# 1. System Health Check Badges
health = get_backend_health()
st.sidebar.markdown("##### System Health Status")

if health["status"] == "healthy":
    st.sidebar.markdown("<span class='badge badge-online'>🟢 FastAPI Online</span>", unsafe_allow_html=True)
    if health["vector_db_loaded"]:
        st.sidebar.markdown("<span class='badge badge-online'>🟢 FAISS DB Active</span>", unsafe_allow_html=True)
    else:
        st.sidebar.markdown("<span class='badge badge-warning'>🟡 FAISS DB Empty</span>", unsafe_allow_html=True)
    if health["openai_initialized"]:
        st.sidebar.markdown(f"<span class='badge badge-online'>🟢 OpenAI Active ({health['openai_model'].split('/')[-1]})</span>", unsafe_allow_html=True)
    else:
        st.sidebar.markdown("<span class='badge badge-warning'>🟡 OpenAI Demo Mode</span>", unsafe_allow_html=True)
else:
    st.sidebar.markdown("<span class='badge badge-offline'>🔴 FastAPI Offline</span>", unsafe_allow_html=True)
    st.sidebar.markdown("<span class='badge badge-offline'>🔴 FAISS DB Offline</span>", unsafe_allow_html=True)
    st.sidebar.markdown("<span class='badge badge-warning'>🟡 Running in Standalone Demo Mode</span>", unsafe_allow_html=True)

st.sidebar.markdown("---")

# 2. Sliders and parameters configurations
st.sidebar.markdown("##### Hyperparameter Tuning")
top_k = st.sidebar.slider(
    "Retrieval Top-K Chunks", 
    min_value=1, 
    max_value=8, 
    value=4
)
temperature = st.sidebar.slider(
    "Creativity / Temperature", 
    min_value=0.0, 
    max_value=1.0, 
    value=0.7, 
    step=0.05
)

st.sidebar.markdown("---")

# 3. Document Ingestion Controller
st.sidebar.markdown("##### Tactical Repository Ingestion")
st.sidebar.info("Add tactical PDFs or blogs to `data/raw` then run Re-Index.")

if st.sidebar.button("⚡ Re-Index Raw Documents", use_container_width=True):
    with st.sidebar.spinner("Scanning and building FAISS embeddings..."):
        ingest_res = trigger_backend_ingestion()
    if ingest_res["status"] == "success":
        st.sidebar.success(
            f"Index Built!\n"
            f"Processed: {ingest_res.get('total_files_processed')}\n"
            f"Chunks: {ingest_res.get('total_chunks_indexed')}"
        )
        st.rerun()
    else:
        st.sidebar.error(f"Ingestion failed: {ingest_res.get('message')}")

st.sidebar.markdown("---")
st.sidebar.markdown("##### 🌐 Dynamic URL Scraper")
url_input = st.sidebar.text_input("Paste Tactical URL (HTML/Blog):", placeholder="https://example.com/blog")
if st.sidebar.button("🕸️ Scrape & Index URL", use_container_width=True):
    if url_input.strip():
        with st.sidebar.spinner("Crawling remote blog URL..."):
            try:
                res = requests.post(f"{BACKEND_URL}/ingest/url", json={"url": url_input.strip()}, timeout=120)
                if res.status_code == 200:
                    data = res.json()
                    st.sidebar.success(f"Indexed {data.get('total_chunks_indexed')} chunks from URL!")
                    st.rerun()
                else:
                    st.sidebar.error(f"Error: {res.json().get('detail', 'Failed to index')}")
            except Exception as e:
                st.sidebar.error(f"Connection error: {str(e)}")
    else:
        st.sidebar.warning("Please paste a valid URL first.")

# 4. Session History Sidebar deck
st.sidebar.markdown("---")
st.sidebar.markdown("<h4 style='color:#10b981; font-family:\"Space Grotesk\"; margin-bottom:0.5rem;'>📜 MY PRIVATE LOGS</h4>", unsafe_allow_html=True)

# Add a New Session Button
if st.sidebar.button("➕ Start New Session", use_container_width=True):
    st.session_state.active_session_id = None
    st.session_state.messages = []
    st.rerun()

# Fetch and display saved sessions (Strict user-tenant token separation)
try:
    headers = {"X-User-Token": st.session_state.token}
    sessions_res = requests.get(f"{BACKEND_URL}/sessions", headers=headers, timeout=3)
    if sessions_res.status_code == 200:
        saved_sessions = sessions_res.json()
        if saved_sessions:
            for s in saved_sessions:
                is_active = st.session_state.get("active_session_id") == s["id"]
                label = f"💬 {s['title']}"
                if is_active:
                    label = f"➡️ 💬 {s['title']}"
                
                if st.sidebar.button(label, key=f"sess_{s['id']}", use_container_width=True):
                    st.session_state.active_session_id = s["id"]
                    msg_res = requests.get(f"{BACKEND_URL}/sessions/{s['id']}/messages", headers=headers, timeout=5)
                    if msg_res.status_code == 200:
                        st.session_state.messages = []
                        for msg in msg_res.json():
                            st.session_state.messages.append({
                                "role": msg["role"],
                                "content": msg["content"],
                                "sources": msg["sources"],
                                "is_web_search_active": any(x.get("type") == "web_search" for x in msg["sources"]),
                                "is_live_matches_active": any(x.get("type") == "live_scores" or "REAL-TIME FOOTBALL LATEST" in x.get("text", "") for x in msg["sources"])
                            })
                        st.rerun()
        else:
            st.sidebar.caption("No personal coaching logs found.")
except Exception:
    st.sidebar.caption("Failed to load coaching logs.")

# Download premium ReportLab PDF Exporter dossier
if st.session_state.get("active_session_id") and st.session_state.get("messages"):
    st.sidebar.markdown("---")
    st.sidebar.markdown("<h4 style='color:#10b981; font-family:\"Space Grotesk\"; margin-bottom:0.5rem;'>💾 TACTICAL PDF EXPORT</h4>", unsafe_allow_html=True)
    
    with st.sidebar.spinner("Compiling ReportLab brochure..."):
        pdf_bytes = download_session_pdf(st.session_state.active_session_id)
        
    if pdf_bytes:
        st.sidebar.download_button(
            label="⚽ Download Styled PDF Dossier",
            data=pdf_bytes,
            file_name=f"footbot_dossier_{st.session_state.active_session_id[:8]}.pdf",
            mime="application/pdf",
            use_container_width=True,
            help="Generates an enterprise-grade multipage PDF brochure with tactical citations, custom headers/footers, and page numbers."
        )
    else:
        st.sidebar.warning("Failed to compile ReportLab PDF.")

st.sidebar.markdown("---")
st.sidebar.markdown("<div style='font-size:0.8rem; color:#6b7280; text-align:center;'>FootBot v1.0.0 • Akilan Flagship AI</div>", unsafe_allow_html=True)

# --- Main Application Tabs Layout ---
tab_chat, tab_pitch, tab_live, tab_sofa = st.tabs(["💬 Tactical AI Chat", "📋 2D Formation Board", "⚽ Live & Historical Scorelines", "📊 SofaScore Match Centre"])

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
    for msg in st.session_state.messages:
        role = msg["role"]
        avatar = "⚽" if role == "assistant" else "👤"
        
        with st.chat_message(role, avatar=avatar):
            if role == "assistant" and msg.get("is_web_search_active"):
                st.markdown("<span class='badge badge-info'>🌐 Live Web Search Fallback Active</span>", unsafe_allow_html=True)
            if role == "assistant" and msg.get("is_live_matches_active"):
                st.markdown("<span class='badge badge-online'>🟢 Live Scores & News Injected</span>", unsafe_allow_html=True)
                
            st.markdown(msg["content"])
            
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
        
    user_input = st.chat_input("Ask FootBot a tactical football question (e.g. Compare Rodri and Busquets)...")
    if user_input:
        query = user_input
        
    # --- RAG Orchestration Flow ---
    if query:
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user", avatar="👤"):
            st.markdown(query)
            
        with st.chat_message("assistant", avatar="⚽"):
            response_placeholder = st.empty()
            spinner_placeholder = st.empty()
            
            with spinner_placeholder:
                st.markdown("*FootBot is consulting hybrid semantic indices & generating tactical analysis...*")
                st.spinner()
                
            result = submit_query_to_backend(query, top_k, temperature, st.session_state.get("active_session_id"))
            spinner_placeholder.empty()
            
            if result.get("is_web_search_active"):
                st.markdown("<span class='badge badge-info'>🌐 Live Web Search Fallback Active</span>", unsafe_allow_html=True)
            if result.get("is_live_matches_active"):
                st.markdown("<span class='badge badge-online'>🟢 Live Scores & News Injected</span>", unsafe_allow_html=True)
                
            response_text = result["response"]
            response_placeholder.markdown(response_text)
            
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
                        
        st.session_state.active_session_id = result.get("session_id")
        st.session_state.messages.append({
            "role": "assistant",
            "content": response_text,
            "sources": sources,
            "is_web_search_active": result.get("is_web_search_active", False),
            "is_live_matches_active": result.get("is_live_matches_active", False)
        })
        st.rerun()

with tab_pitch:
    st.markdown("<h3 style='color:#10b981; font-family:\"Space Grotesk\"; margin-top:0;'>📋 Drag-and-Drop 2D Formation customizer</h3>", unsafe_allow_html=True)
    st.markdown("Visual spatial planner mapping coaching formations directly to RAG semantic analysis query vectors.")
    
    col_map, col_form = st.columns([1, 1])
    
    with col_form:
        st.markdown("#### Configure Formation Parameters")
        sel_formation = st.selectbox(
            "Select Base Tactical Shape:",
            ["Pep's 3-2-4-1 resting shape", "Arteta's 4-3-3 Hybrid", "Klopp's 4-3-3 high-intensity Gegenpress", "Custom 5-4-1 defensive low block", "Ancelotti's 4-4-2 Diamond"]
        )
        
        sel_pressing = st.select_slider(
            "Select Pressing Line Block Height:",
            options=["High pressing swarm", "Mid-block compression", "Low block deep compact fence"]
        )
        
        opt_inverted = st.toggle("Enable Inverted Fullback (steps inside double pivot)", value=False)
        opt_wingers = st.radio(
            "Attacking Wingers Placement Style:",
            ["Pinned wide on the touchlines", "Inverted interior inside-forwards"]
        )
        opt_midfield = st.radio(
            "Central Midfield Shape Geometry:",
            ["Box (Double Pivot + Double 10s)", "Flat Trio / Central triangle", "Single Pivot + Double attacking 8s"]
        )
        
        with st.expander("✏️ Customize Player Labels"):
            custom_lw = st.text_input("Left Winger label:", value="LW")
            custom_rw = st.text_input("Right Winger label:", value="RW")
            custom_cf = st.text_input("Center Forward label:", value="CF")
            custom_am = st.text_input("Attacking Midfielder label:", value="AM")
            custom_cm = st.text_input("Central Midfielder label:", value="CM")
            custom_dm = st.text_input("Defensive Midfielder label:", value="DM")
            custom_cb = st.text_input("Center Back label:", value="CB")
            custom_gk = st.text_input("Goalkeeper label:", value="GK")
            
        assess_button = st.button("🧠 Submit Formation for RAG Assessment", use_container_width=True)
        
    with col_map:
        st.markdown("#### Live 2D Tactical Pitch Preview")
        
        # Build mathematically aligned ASCII pitch representation
        WIDTH = 38
        
        def format_line(content: str) -> str:
            # Centered padding guaranteeing exactly WIDTH characters inside the borders
            if len(content) < WIDTH:
                left = (WIDTH - len(content)) // 2
                right = WIDTH - len(content) - left
                return f" │ {' ' * left}{content}{' ' * right} │ "
            return f" │ {content[:WIDTH]} │ "
            
        lines = [
            f" ┌{'─' * (WIDTH + 2)}┐ ",
            format_line("[ OPPONENT GOAL ]"),
            f" ├{'─' * (WIDTH + 2)}┤ "
        ]
        
        w_l = custom_lw if "wide" in opt_wingers.lower() else f"{custom_lw} (Inside)"
        w_r = custom_rw if "wide" in opt_wingers.lower() else f"{custom_rw} (Inside)"
        
        if "3-2-4-1" in sel_formation:
            lines.append(format_line(f"{custom_cf}"))
            lines.append(format_line(""))
            lines.append(format_line(f"{w_l}     {custom_am}     {custom_am}     {w_r}"))
            lines.append(format_line(""))
            lines.append(format_line(f"{custom_dm}     {custom_dm}"))
            lines.append(format_line(""))
            lines.append(format_line(f"{custom_cb}     {custom_cb}     {custom_cb}"))
        elif "4-3-3" in sel_formation:
            lines.append(format_line(f"{w_l}        {custom_cf}        {w_r}"))
            lines.append(format_line(""))
            if "Box" in opt_midfield:
                lines.append(format_line(f"{custom_am}            {custom_am}"))
                lines.append(format_line(f"{custom_dm}"))
            else:
                lines.append(format_line(f"{custom_cm}            {custom_cm}"))
                lines.append(format_line(f"{custom_dm}"))
            lines.append(format_line(""))
            if opt_inverted:
                lines.append(format_line(f"LB      {custom_cb}      {custom_cb}      RB (Inv)"))
            else:
                lines.append(format_line(f"LB      {custom_cb}      {custom_cb}      RB"))
        elif "5-4-1" in sel_formation:
            lines.append(format_line(f"{custom_cf}"))
            lines.append(format_line(f"{w_l}                  {w_r}"))
            lines.append(format_line(f"{custom_cm}     {custom_cm}"))
            lines.append(format_line(""))
            lines.append(format_line(f"LWB   {custom_cb}   {custom_cb}   {custom_cb}   RWB"))
        else: # 4-4-2 Diamond
            lines.append(format_line(f"{custom_cf}            {custom_cf}"))
            lines.append(format_line(""))
            lines.append(format_line(f"{custom_am}"))
            lines.append(format_line(f"LM            RM"))
            lines.append(format_line(f"{custom_dm}"))
            lines.append(format_line(f"LB      {custom_cb}      {custom_cb}      RB"))
            
        lines.extend([
            format_line(""),
            f" ├{'─' * (WIDTH + 2)}┤ ",
            format_line(f"[ {custom_gk} ]"),
            f" └{'─' * (WIDTH + 2)}┘ "
        ])
        
        pitch_ascii = "\n".join(lines)
        
        st.code(pitch_ascii, language="text")
        st.markdown(f"<p style='color:#9ca3af; font-size:0.85rem; margin-top:0.4rem; text-align:center;'>Pressing Height: <b>{sel_pressing.upper()}</b></p>", unsafe_allow_html=True)
        
    if assess_button:
        # Construct tactical query
        tactical_prompt = (
            f"Analyze the tactical strengths, rest-defense security, pressing lines, and space utilization "
            f"of a {sel_formation} formation operating under a {sel_pressing}. "
            f"Configurations: Inverted Fullbacks={'Active' if opt_inverted else 'Inactive'}, "
            f"Attacking Wingers style={opt_wingers}, Midfield Shape={opt_midfield}."
        )
        st.session_state.clicked_preset = tactical_prompt
        st.success("Tactical shape captured! Switching to AI Chat to generate assessment...")
        st.rerun()

with tab_live:
    st.markdown("<h3 style='color:#10b981; font-family:\"Space Grotesk\"; margin-top:0;'>⚽ Live match tracker & Historical Scores</h3>", unsafe_allow_html=True)
    
    col_scores, col_history = st.columns([1, 1])
    
    with col_scores:
        st.markdown("#### 🏆 Live Fixtures & Headlines (BBC RSS)")
        if st.button("🔄 Refresh Live Feed", use_container_width=True):
            st.rerun()
            
        with st.spinner("Crawling live matches..."):
            feed_data = get_live_matches_feed()
            
        if feed_data.get("status") == "success" and feed_data.get("feed"):
            feed = feed_data.get("feed")
            matches = [f for f in feed if f.get("is_match")]
            news = [f for f in feed if not f.get("is_match")]
            
            st.markdown(f"**Live Matches ({len(matches)}):**")
            for m in matches[:6]:
                st.markdown(f"""
                <div class='metric-card hover-effect'>
                    <span class='badge badge-info'>🏆 {m.get('league', 'Football')}</span>
                    <h5 style='color:#34d399; margin:0;'>{m['title']}</h5>
                    <p style='color:#9ca3af; font-size:0.85rem; margin-top:0.3rem; margin-bottom:0.4rem;'>{m['description']}</p>
                    <a href='{m['link']}' target='_blank' style='color:#10b981; font-size:0.8rem; text-decoration:none;'>🔗 Match Centre Updates</a>
                </div>
                """, unsafe_allow_html=True)
                
            st.markdown(f"**Latest News Headlines ({len(news)}):**")
            for n in news[:6]:
                st.markdown(f"""
                <div class='metric-card hover-effect'>
                    <h5 style='color:#f3f4f6; margin:0;'>📢 {n['title']}</h5>
                    <p style='color:#9ca3af; font-size:0.8rem; margin-top:0.3rem; margin-bottom:0.4rem;'>{n['description']}</p>
                    <a href='{n['link']}' target='_blank' style='color:#3b82f6; font-size:0.8rem; text-decoration:none;'>🔗 Read Full Report</a>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No live match scores available.")
            
    with col_history:
        st.markdown("#### 💾 SQLite Historical Match Database")
        
        # Scrape trigger button
        if st.button("⚡ Crawl & Sync Past BBC Results", use_container_width=True, help="Triggers BeautifulSoup crawler on BBC Results page to fetch recently completed scores and store them in SQLite."):
            with st.spinner("Scraping results from BBC Sport..."):
                try:
                    res = requests.post(f"{BACKEND_URL}/historical-matches/crawl", timeout=30)
                    if res.status_code == 200:
                        st.success(res.json().get("message", "Crawled successfully!"))
                        st.rerun()
                    else:
                        st.error(f"Error crawling: {res.text}")
                except Exception as e:
                    st.error(f"Failed to connect to backend: {str(e)}")
                    
        historical_matches = get_historical_matches_feed()
        if historical_matches:
            st.markdown(f"**Saved Completed Matches ({len(historical_matches)}):**")
            for m in historical_matches:
                home_score = m["home_score"] if m["home_score"] is not None else "?"
                away_score = m["away_score"] if m["away_score"] is not None else "?"
                st.markdown(f"""
                <div class='metric-card hover-effect' style='background-color:#050c09; border:1px solid #0d9488;'>
                    <span class='badge badge-online' style='margin-bottom:0.4rem;'>Completed • {m['match_date']}</span>
                    <h5 style='color:#f3f4f6; margin:0;'>📊 {m['home_team']} {home_score} - {away_score} {m['away_team']}</h5>
                    <p style='color:#64748b; font-size:0.8rem; margin:0.3rem 0 0 0;'>Competition: <b>{m['league']}</b></p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Historical match database is empty. Click the crawl button above to populate completed matches.")

with tab_sofa:
    st.markdown("<h3 style='color:#10b981; font-family:\"Space Grotesk\"; margin-top:0;'>📊 SofaScore Premium Match Centre</h3>", unsafe_allow_html=True)
    st.markdown("Advanced minute-by-minute attacking momentum tracking, squad comparison statistics, and positional performance heatmaps.")
    
    # 1. Match Selector - Dynamic Live matches & Completed SQLite results
    # Load live matches in real-time
    live_options = []
    try:
        feed_data = get_live_matches_feed()
        if feed_data.get("status") == "success":
            feed = feed_data.get("feed", [])
            for m in feed:
                if m.get("is_match"):
                    live_options.append(f"🟢 [LIVE] {m['title']} ({m.get('league', 'Live Match')})")
    except Exception:
        pass
        
    # Load completed SQLite matches
    completed_options = []
    historical_matches = get_historical_matches_feed()
    if historical_matches:
        for m in historical_matches:
            hs = m["home_score"] if m["home_score"] is not None else 0
            as_ = m["away_score"] if m["away_score"] is not None else 0
            completed_options.append(f"🏆 [COMPLETED] {m['home_team']} {hs} - {as_} {m['away_team']} ({m['match_date']})")
            
    # Fallback defaults if lists are empty
    default_options = [
        "🏆 [COMPLETED] Manchester City 3 - 3 Real Madrid (Champions League)",
        "🏆 [COMPLETED] Arsenal 2 - 2 Bayern Munich (Champions League)",
        "🏆 [COMPLETED] Liverpool 1 - 1 Manchester City (Premier League)"
    ]
    
    match_options = live_options + completed_options
    if not match_options:
        match_options = default_options
        
    selected_match = st.selectbox("Select Match to Analyze:", options=match_options)
    
    # Clean selected match name for professional RAG prompts
    clean_match_name = selected_match.replace("🏆 [COMPLETED] ", "").replace("🟢 [LIVE] ", "").split(" (")[0]
    
    col_mom, col_stats = st.columns([7, 5])
    
    with col_mom:
        st.markdown("#### 📈 SofaScore Attacking Momentum (Pressure Graph)")
        st.caption("Positive peaks show Home Team dominance; Negative peaks show Away Team dominance.")
        
        # Generate momentum timeline based on selected match seed
        import pandas as pd
        import numpy as np
        import hashlib
        
        seed_val = int(hashlib.md5(selected_match.encode()).hexdigest(), 16) % 10000
        np.random.seed(seed_val)
        
        minutes = list(range(1, 91))
        # Simulated attacking pressure
        h_pres = np.random.normal(25, 25, 90)
        a_pres = np.random.normal(-25, 25, 90)
        
        h_pres = np.clip(h_pres, 0, 100)
        a_pres = np.clip(a_pres, -100, 0)
        
        # Smoothing moving average filter
        h_pres = np.convolve(h_pres, np.ones(5)/5, mode='same')
        a_pres = np.convolve(a_pres, np.ones(5)/5, mode='same')
        
        mom_df = pd.DataFrame({
            "Home Pressure": h_pres,
            "Away Pressure": a_pres
        }, index=minutes)
        
        # Plot styled Streamlit Area Chart (uninteractive/unzoomable as requested)
        st.area_chart(mom_df, use_container_width=True, interactive=False)
        
    with col_stats:
        st.markdown("#### 📊 Match Box Score Comparison")
        
        # Deterministic stats based on seed
        possession_home = int(np.clip(np.random.normal(52, 8), 35, 65))
        possession_away = 100 - possession_home
        
        shots_home = int(np.clip(np.random.normal(14, 4), 5, 25))
        shots_away = int(np.clip(np.random.normal(11, 3), 4, 20))
        
        chances_home = int(np.clip(np.random.normal(3, 1.5), 0, 8))
        chances_away = int(np.clip(np.random.normal(2, 1.2), 0, 6))
        
        passes_home = possession_home * 8 + int(np.random.normal(50, 10))
        passes_away = possession_away * 8 + int(np.random.normal(50, 10))
        
        def render_stat_row(label: str, home_val: int, away_val: int, is_percent: bool = False):
            total = home_val + away_val
            home_ratio = (home_val / max(1, total)) * 100
            away_ratio = 100 - home_ratio
            suffix = "%" if is_percent else ""
            st.markdown(f"""
            <div style="margin-bottom: 0.8rem;">
                <div style="display: flex; justify-content: space-between; font-size: 0.9rem; margin-bottom: 0.2rem; color: #9ca3af;">
                    <span><b>{home_val}{suffix}</b></span>
                    <span style="color: #f3f4f6; font-weight: 600;">{label}</span>
                    <span><b>{away_val}{suffix}</b></span>
                </div>
                <div style="display: flex; height: 6px; border-radius: 3px; overflow: hidden; background-color: #1f2937;">
                    <div style="width: {home_ratio}%; background-color: #10b981;"></div>
                    <div style="width: {away_ratio}%; background-color: #4b5563;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        render_stat_row("Ball Possession", possession_home, possession_away, is_percent=True)
        render_stat_row("Total Shots", shots_home, shots_away)
        render_stat_row("Big Chances Created", chances_home, chances_away)
        render_stat_row("Accurate Passes Completed", passes_home, passes_away)
        
    # --- SofaScore Visual Match Ratings & Lineups Pitch ---
    st.markdown("---")
    st.markdown("<h3 style='color:#10b981; font-family:\"Space Grotesk\"; margin-top:0;'>🏟️ SofaScore Tactical Lineups & Match Ratings</h3>", unsafe_allow_html=True)
    
    # Clean home/away team names
    clean_title = selected_match.replace("🏆 [COMPLETED] ", "").replace("🟢 [LIVE] ", "")
    if " (" in clean_title:
        clean_title = clean_title.split(" (")[0]
        
    import re
    team_parts = re.split(r'\s+\d+\s*-\s*\d+\s+|\s+vs\s+', clean_title)
    if len(team_parts) >= 2:
        home_team_name = team_parts[0].strip()
        away_team_name = team_parts[1].strip()
    else:
        home_team_name = "Home Team"
        away_team_name = "Away Team"
        
    # Helper to load base64 image
    import base64
    import os
    def get_image_base64(path):
        try:
            if path and os.path.exists(path):
                mime = "image/png"
                if path.endswith(".svg"):
                    mime = "image/svg+xml"
                elif path.endswith(".jpg") or path.endswith(".jpeg"):
                    mime = "image/jpeg"
                with open(path, "rb") as image_file:
                    encoded = base64.b64encode(image_file.read()).decode()
                    return f"data:{mime};base64,{encoded}"
        except Exception:
            pass
        return ""
        
    # Helper to strip leading whitespace from HTML strings to prevent Markdown preformatted/code block interpretation
    def clean_html(html_str):
        return "\n".join(line.strip() for line in html_str.split("\n"))

    # Roster mapping function
    def get_team_roster(team_name: str, is_home: bool):
        name_norm = team_name.lower().strip()
        
        # Try fetching real-world roster from backend API first
        try:
            import requests
            response = requests.get(f"{BACKEND_URL}/roster", params={"team_name": team_name}, timeout=35)
            if response.status_code == 200:
                res_data = response.json()
                if res_data.get("status") == "success" and res_data.get("roster"):
                    return res_data["roster"]
        except Exception:
            pass

        roster_data = {
            "manchester city": [
                {"name": "Ederson", "jersey": "31", "rating": 6.2, "pos": "GK", "photo": "frontend/assets/ederson.png", "age": "32", "val": "€35M", "height": "188 cm"},
                {"name": "K. Walker", "jersey": "2", "rating": 6.8, "pos": "RB", "photo": "", "age": "35", "val": "€15M", "height": "183 cm"},
                {"name": "R. Dias", "jersey": "3", "rating": 7.2, "pos": "RCB", "photo": "frontend/assets/dias.png", "age": "28", "val": "€80M", "height": "187 cm"},
                {"name": "M. Akanji", "jersey": "25", "rating": 7.0, "pos": "LCB", "photo": "", "age": "30", "val": "€45M", "height": "187 cm"},
                {"name": "J. Gvardiol", "jersey": "24", "rating": 7.5, "pos": "LB", "photo": "", "age": "24", "val": "€75M", "height": "185 cm"},
                {"name": "Rodri", "jersey": "16", "rating": 8.0, "pos": "LDM", "photo": "frontend/assets/rodri.png", "age": "29", "val": "€120M", "height": "190 cm"},
                {"name": "J. Stones", "jersey": "5", "rating": 6.8, "pos": "RDM", "photo": "", "age": "31", "val": "€38M", "height": "188 cm"},
                {"name": "B. Silva", "jersey": "20", "rating": 8.2, "pos": "RAM", "photo": "frontend/assets/silva.png", "age": "31", "val": "€70M", "height": "173 cm"},
                {"name": "K. De Bruyne", "jersey": "17", "rating": 8.5, "pos": "CAM", "photo": "frontend/assets/debruyne.png", "age": "34", "val": "€60M", "height": "181 cm"},
                {"name": "P. Foden", "jersey": "47", "rating": 8.7, "pos": "LAM", "photo": "frontend/assets/foden.png", "age": "25", "val": "€150M", "height": "179 cm"},
                {"name": "E. Haaland", "jersey": "9", "rating": 8.4, "pos": "ST", "photo": "frontend/assets/haaland.png", "age": "25", "val": "€180M", "height": "194 cm"},
            ],
            "real madrid": [
                {"name": "A. Lunin", "jersey": "13", "rating": 6.5, "pos": "GK", "photo": "", "age": "27", "val": "€25M", "height": "191 cm"},
                {"name": "D. Carvajal", "jersey": "2", "rating": 7.0, "pos": "RB", "photo": "", "age": "34", "val": "€12M", "height": "173 cm"},
                {"name": "A. Rüdiger", "jersey": "22", "rating": 7.8, "pos": "RCB", "photo": "", "age": "33", "val": "€25M", "height": "190 cm"},
                {"name": "Nacho", "jersey": "6", "rating": 6.4, "pos": "LCB", "photo": "", "age": "36", "val": "€4M", "height": "180 cm"},
                {"name": "F. Mendy", "jersey": "23", "rating": 6.6, "pos": "LB", "photo": "", "age": "30", "val": "€20M", "height": "180 cm"},
                {"name": "F. Valverde", "jersey": "15", "rating": 7.4, "pos": "RCM", "photo": "", "age": "27", "val": "€100M", "height": "182 cm"},
                {"name": "T. Kroos", "jersey": "8", "rating": 8.1, "pos": "CM", "photo": "", "age": "36", "val": "€10M", "height": "183 cm"},
                {"name": "E. Camavinga", "jersey": "12", "rating": 7.2, "pos": "LCM", "photo": "", "age": "23", "val": "€90M", "height": "182 cm"},
                {"name": "J. Bellingham", "jersey": "5", "rating": 8.3, "pos": "AM", "photo": "frontend/assets/bellingham.jpg", "age": "22", "val": "€180M", "height": "186 cm"},
                {"name": "Vinícius Jr.", "jersey": "7", "rating": 8.6, "pos": "LST", "photo": "", "age": "25", "val": "€150M", "height": "176 cm"},
                {"name": "Rodrygo", "jersey": "11", "rating": 7.9, "pos": "RST", "photo": "", "age": "25", "val": "€100M", "height": "174 cm"},
            ],
            "bayern": [
                {"name": "M. Neuer", "jersey": "1", "rating": 5.9, "pos": "GK", "photo": "", "age": "40", "val": "€5M", "height": "193 cm"},
                {"name": "J. Kimmich", "jersey": "6", "rating": 8.6, "pos": "RB", "photo": "", "age": "31", "val": "€50M", "height": "177 cm"},
                {"name": "M. de Ligt", "jersey": "4", "rating": 7.0, "pos": "RCB", "photo": "", "age": "26", "val": "€65M", "height": "188 cm"},
                {"name": "E. Dier", "jersey": "15", "rating": 6.4, "pos": "LCB", "photo": "", "age": "32", "val": "€12M", "height": "188 cm"},
                {"name": "N. Mazraoui", "jersey": "40", "rating": 6.8, "pos": "LB", "photo": "", "age": "28", "val": "€30M", "height": "183 cm"},
                {"name": "K. Laimer", "jersey": "27", "rating": 6.1, "pos": "LDM", "photo": "", "age": "29", "val": "€30M", "height": "180 cm"},
                {"name": "A. Pavlović", "jersey": "45", "rating": 8.1, "pos": "RDM", "photo": "", "age": "22", "val": "€25M", "height": "188 cm"},
                {"name": "L. Sané", "jersey": "10", "rating": 7.8, "pos": "RAM", "photo": "", "age": "30", "val": "€70M", "height": "183 cm"},
                {"name": "T. Müller", "jersey": "25", "rating": 7.2, "pos": "CAM", "photo": "", "age": "36", "val": "€8M", "height": "185 cm"},
                {"name": "J. Musiala", "jersey": "42", "rating": 8.5, "pos": "LAM", "photo": "", "age": "23", "val": "€110M", "height": "184 cm"},
                {"name": "H. Kane", "jersey": "9", "rating": 8.0, "pos": "ST", "photo": "", "age": "32", "val": "€110M", "height": "188 cm"},
            ],
            "arsenal": [
                {"name": "D. Raya", "jersey": "22", "rating": 6.8, "pos": "GK", "photo": "", "age": "30", "val": "€35M", "height": "183 cm"},
                {"name": "B. White", "jersey": "4", "rating": 7.2, "pos": "RB", "photo": "", "age": "28", "val": "€55M", "height": "186 cm"},
                {"name": "W. Saliba", "jersey": "2", "rating": 7.7, "pos": "RCB", "photo": "", "age": "25", "val": "€80M", "height": "192 cm"},
                {"name": "G. Magalhães", "jersey": "6", "rating": 7.3, "pos": "LCB", "photo": "", "age": "28", "val": "€65M", "height": "190 cm"},
                {"name": "J. Kiwior", "jersey": "15", "rating": 6.4, "pos": "LB", "photo": "", "age": "26", "val": "€25M", "height": "189 cm"},
                {"name": "D. Rice", "jersey": "41", "rating": 8.0, "pos": "LCM", "photo": "", "age": "27", "val": "€110M", "height": "185 cm"},
                {"name": "Jorginho", "jersey": "20", "rating": 7.1, "pos": "RCM", "photo": "", "age": "34", "val": "€15M", "height": "180 cm"},
                {"name": "M. Ødegaard", "jersey": "8", "rating": 8.4, "pos": "AM", "photo": "", "age": "27", "val": "€95M", "height": "178 cm"},
                {"name": "B. Saka", "jersey": "7", "rating": 8.2, "pos": "RW", "photo": "", "age": "24", "val": "€130M", "height": "178 cm"},
                {"name": "G. Martinelli", "jersey": "11", "rating": 7.5, "pos": "LW", "photo": "", "age": "24", "val": "€80M", "height": "178 cm"},
                {"name": "K. Havertz", "jersey": "29", "rating": 7.9, "pos": "ST", "photo": "", "age": "26", "val": "€60M", "height": "193 cm"},
            ],
            "haiti": [
                {"name": "Duverger", "jersey": "1", "rating": 6.8, "pos": "GK", "photo": "", "age": "26", "val": "€500K", "height": "188 cm"},
                {"name": "Gérard", "jersey": "2", "rating": 7.2, "pos": "RB", "photo": "", "age": "24", "val": "€300K", "height": "178 cm"},
                {"name": "Arise", "jersey": "4", "rating": 7.5, "pos": "RCB", "photo": "", "age": "25", "val": "€450K", "height": "185 cm"},
                {"name": "Adé", "jersey": "6", "rating": 7.1, "pos": "LCB", "photo": "", "age": "31", "val": "€200K", "height": "190 cm"},
                {"name": "Lacroix", "jersey": "3", "rating": 8.3, "pos": "LB", "photo": "", "age": "32", "val": "€400K", "height": "179 cm"},
                {"name": "Alceus", "jersey": "8", "rating": 7.0, "pos": "LCM", "photo": "", "age": "29", "val": "€350K", "height": "177 cm"},
                {"name": "L. Joseph", "jersey": "14", "rating": 8.1, "pos": "RCM", "photo": "", "age": "25", "val": "€1M", "height": "185 cm"},
                {"name": "R. Providence", "jersey": "10", "rating": 8.4, "pos": "AM", "photo": "", "age": "24", "val": "€2M", "height": "179 cm"},
                {"name": "Antoine", "jersey": "7", "rating": 6.9, "pos": "RW", "photo": "", "age": "32", "val": "€600K", "height": "178 cm"},
                {"name": "F. Pierrot", "jersey": "9", "rating": 8.6, "pos": "ST", "photo": "", "age": "31", "val": "€4M", "height": "194 cm"},
                {"name": "Nazon", "jersey": "11", "rating": 7.4, "pos": "LW", "photo": "", "age": "31", "val": "€1.5M", "height": "181 cm"},
            ],
            "new zealand": [
                {"name": "Paulsen", "jersey": "12", "rating": 5.8, "pos": "GK", "photo": "", "age": "23", "val": "€1M", "height": "195 cm"},
                {"name": "Payne", "jersey": "2", "rating": 5.4, "pos": "RB", "photo": "", "age": "32", "val": "€500K", "height": "188 cm"},
                {"name": "Boxall", "jersey": "4", "rating": 6.0, "pos": "RCB", "photo": "", "age": "37", "val": "€200K", "height": "188 cm"},
                {"name": "Bindon", "jersey": "6", "rating": 6.2, "pos": "LCB", "photo": "", "age": "21", "val": "€600K", "height": "186 cm"},
                {"name": "Cacace", "jersey": "3", "rating": 6.7, "pos": "LB", "photo": "", "age": "25", "val": "€3M", "height": "183 cm"},
                {"name": "Bell", "jersey": "8", "rating": 6.1, "pos": "LDM", "photo": "", "age": "26", "val": "€1.2M", "height": "182 cm"},
                {"name": "Howieson", "jersey": "10", "rating": 5.9, "pos": "RDM", "photo": "", "age": "31", "val": "€400K", "height": "180 cm"},
                {"name": "Ruffer", "jersey": "7", "rating": 6.2, "pos": "RAM", "photo": "", "age": "25", "val": "€350K", "height": "178 cm"},
                {"name": "Just", "jersey": "14", "rating": 6.5, "pos": "CAM", "photo": "", "age": "25", "val": "€500K", "height": "177 cm"},
                {"name": "Garbett", "jersey": "11", "rating": 6.3, "pos": "LAM", "photo": "", "age": "24", "val": "€1.5M", "height": "188 cm"},
                {"name": "Wood", "jersey": "9", "rating": 6.1, "pos": "ST", "photo": "", "age": "34", "val": "€6M", "height": "191 cm"},
            ],
            "spain": [
                {"name": "U. Simón", "jersey": "23", "rating": 6.9, "pos": "GK", "photo": "", "age": "28", "val": "€30M", "height": "190 cm"},
                {"name": "M. Llorente", "jersey": "5", "rating": 6.6, "pos": "RB", "photo": "", "age": "31", "val": "€30M", "height": "184 cm"},
                {"name": "P. Cubarsí", "jersey": "22", "rating": 7.5, "pos": "RCB", "photo": "", "age": "19", "val": "€40M", "height": "184 cm"},
                {"name": "A. Laporte", "jersey": "14", "rating": 7.0, "pos": "LCB", "photo": "", "age": "32", "val": "€20M", "height": "191 cm"},
                {"name": "M. Cucurella", "jersey": "24", "rating": 6.2, "pos": "LB", "photo": "", "age": "27", "val": "€25M", "height": "173 cm"},
                {"name": "Pedri", "jersey": "20", "rating": 7.7, "pos": "RDM", "photo": "", "age": "23", "val": "€80M", "height": "174 cm"},
                {"name": "Rodri", "jersey": "16", "rating": 7.7, "pos": "LDM", "photo": "", "age": "29", "val": "€120M", "height": "190 cm"},
                {"name": "A. Baena", "jersey": "15", "rating": 6.5, "pos": "RAM", "photo": "", "age": "24", "val": "€40M", "height": "177 cm"},
                {"name": "F. Ruiz", "jersey": "8", "rating": 6.7, "pos": "CAM", "photo": "", "age": "30", "val": "€30M", "height": "189 cm"},
                {"name": "F. Torres", "jersey": "7", "rating": 6.9, "pos": "LAM", "photo": "", "age": "26", "val": "€35M", "height": "184 cm"},
                {"name": "M. Oyarzabal", "jersey": "21", "rating": 6.7, "pos": "ST", "photo": "", "age": "29", "val": "€40M", "height": "181 cm"},
            ],
            "peru": [
                {"name": "P. Gallese", "jersey": "1", "rating": 5.4, "pos": "GK", "photo": "", "age": "36", "val": "€1.5M", "height": "189 cm"},
                {"name": "J. Vidales", "jersey": "27", "rating": 6.5, "pos": "RB", "photo": "", "age": "33", "val": "€300K", "height": "175 cm"},
                {"name": "R. Garces", "jersey": "15", "rating": 6.4, "pos": "RCB", "photo": "", "age": "29", "val": "€700K", "height": "183 cm"},
                {"name": "F. Gruber", "jersey": "3", "rating": 6.1, "pos": "LCB", "photo": "", "age": "23", "val": "€400K", "height": "188 cm"},
                {"name": "O. Sonne", "jersey": "22", "rating": 5.9, "pos": "LB", "photo": "", "age": "25", "val": "€1.2M", "height": "187 cm"},
                {"name": "J. Pretell", "jersey": "6", "rating": 6.3, "pos": "RDM", "photo": "", "age": "26", "val": "€600K", "height": "170 cm"},
                {"name": "E. Noriega", "jersey": "8", "rating": 6.4, "pos": "LDM", "photo": "", "age": "24", "val": "€500K", "height": "178 cm"},
                {"name": "J. Vélez", "jersey": "11", "rating": 8.1, "pos": "RAM", "photo": "", "age": "29", "val": "€1M", "height": "176 cm"},
                {"name": "Y. Yotún", "jersey": "19", "rating": 6.6, "pos": "CAM", "photo": "", "age": "36", "val": "€1.5M", "height": "171 cm"},
                {"name": "M. López", "jersey": "4", "rating": 6.6, "pos": "LAM", "photo": "", "age": "26", "val": "€2M", "height": "176 cm"},
                {"name": "A. Ugarriza", "jersey": "9", "rating": 6.3, "pos": "ST", "photo": "", "age": "29", "val": "€500K", "height": "181 cm"},
            ],
            "liverpool": [
                {"name": "Alisson B.", "jersey": "1", "rating": 7.5, "pos": "GK", "photo": "", "age": "33", "val": "€28M", "height": "193 cm"},
                {"name": "Alexander-Arnold", "jersey": "66", "rating": 7.8, "pos": "RB", "photo": "", "age": "27", "val": "€70M", "height": "180 cm"},
                {"name": "I. Konaté", "jersey": "5", "rating": 7.1, "pos": "RCB", "photo": "", "age": "27", "val": "€45M", "height": "194 cm"},
                {"name": "V. van Dijk", "jersey": "4", "rating": 8.2, "pos": "LCB", "photo": "", "age": "34", "val": "€30M", "height": "193 cm"},
                {"name": "A. Robertson", "jersey": "26", "rating": 7.2, "pos": "LB", "photo": "", "age": "32", "val": "€30M", "height": "178 cm"},
                {"name": "W. Endo", "jersey": "3", "rating": 6.9, "pos": "RDM", "photo": "", "age": "33", "val": "€13M", "height": "178 cm"},
                {"name": "Mac Allister", "jersey": "10", "rating": 7.6, "pos": "LDM", "photo": "", "age": "27", "val": "€75M", "height": "176 cm"},
                {"name": "Mohamed Salah", "jersey": "11", "rating": 8.4, "pos": "RAM", "photo": "", "age": "33", "val": "€55M", "height": "175 cm"},
                {"name": "Szoboszlai", "jersey": "8", "rating": 7.3, "pos": "CAM", "photo": "", "age": "25", "val": "€75M", "height": "187 cm"},
                {"name": "L. Díaz", "jersey": "7", "rating": 7.7, "pos": "LAM", "photo": "", "age": "29", "val": "€75M", "height": "180 cm"},
                {"name": "D. Núñez", "jersey": "9", "rating": 7.4, "pos": "ST", "photo": "", "age": "26", "val": "€65M", "height": "187 cm"},
            ],
            "philippines": [
                {"name": "N. Etheridge", "jersey": "1", "rating": 6.7, "pos": "GK", "photo": "", "age": "36", "val": "€350K", "height": "188 cm"},
                {"name": "C. de Murga", "jersey": "2", "rating": 6.2, "pos": "RB", "photo": "", "age": "39", "val": "€50K", "height": "180 cm"},
                {"name": "A. Aguinaldo", "jersey": "12", "rating": 6.4, "pos": "RCB", "photo": "", "age": "30", "val": "€150K", "height": "180 cm"},
                {"name": "C. Rontini", "jersey": "4", "rating": 6.3, "pos": "LCB", "photo": "", "age": "25", "val": "€150K", "height": "186 cm"},
                {"name": "D. Sato", "jersey": "11", "rating": 6.5, "pos": "LB", "photo": "", "age": "31", "val": "€200K", "height": "170 cm"},
                {"name": "Manny Ott", "jersey": "8", "rating": 6.6, "pos": "RDM", "photo": "", "age": "34", "val": "€200K", "height": "172 cm"},
                {"name": "K. Ingreso", "jersey": "14", "rating": 6.3, "pos": "LDM", "photo": "", "age": "31", "val": "€150K", "height": "178 cm"},
                {"name": "OJ Porteria", "jersey": "7", "rating": 6.8, "pos": "RAM", "photo": "", "age": "32", "val": "€200K", "height": "167 cm"},
                {"name": "Mike Ott", "jersey": "10", "rating": 6.9, "pos": "CAM", "photo": "", "age": "31", "val": "€225K", "height": "168 cm"},
                {"name": "S. Schröck", "jersey": "17", "rating": 7.0, "pos": "LAM", "photo": "", "age": "39", "val": "€50K", "height": "170 cm"},
                {"name": "P. Reichelt", "jersey": "9", "rating": 6.8, "pos": "ST", "photo": "", "age": "37", "val": "€100K", "height": "180 cm"},
            ],
            "guam": [
                {"name": "D. Jaye", "jersey": "1", "rating": 5.9, "pos": "GK", "photo": "", "age": "32", "val": "€50K", "height": "187 cm"},
                {"name": "Alex Lee", "jersey": "2", "rating": 5.8, "pos": "RB", "photo": "", "age": "36", "val": "€25K", "height": "178 cm"},
                {"name": "T. Nicklaw", "jersey": "4", "rating": 6.0, "pos": "RCB", "photo": "", "age": "34", "val": "€50K", "height": "181 cm"},
                {"name": "M. Grimes", "jersey": "5", "rating": 5.9, "pos": "LCB", "photo": "", "age": "33", "val": "€25K", "height": "185 cm"},
                {"name": "J. Grindeland", "jersey": "3", "rating": 5.7, "pos": "LB", "photo": "", "age": "28", "val": "€10K", "height": "175 cm"},
                {"name": "M. Chargualaf", "jersey": "8", "rating": 6.0, "pos": "RDM", "photo": "", "age": "36", "val": "€10K", "height": "170 cm"},
                {"name": "I. Mariano", "jersey": "10", "rating": 6.1, "pos": "LDM", "photo": "", "age": "38", "val": "€10K", "height": "172 cm"},
                {"name": "M. Lopez", "jersey": "7", "rating": 6.2, "pos": "RAM", "photo": "", "age": "34", "val": "€50K", "height": "175 cm"},
                {"name": "J. Cunliffe", "jersey": "11", "rating": 6.5, "pos": "CAM", "photo": "", "age": "42", "val": "€10K", "height": "170 cm"},
                {"name": "S. Spindel", "jersey": "9", "rating": 5.9, "pos": "LAM", "photo": "", "age": "35", "val": "€10K", "height": "174 cm"},
                {"name": "S. Malcolm", "jersey": "19", "rating": 6.1, "pos": "ST", "photo": "", "age": "34", "val": "€50K", "height": "182 cm"},
            ],
            "japan": [
                {"name": "Z. Suzuki", "jersey": "1", "rating": 7.0, "pos": "GK", "photo": "", "age": "23", "val": "€15M", "height": "190 cm"},
                {"name": "Y. Sugawara", "jersey": "2", "rating": 7.2, "pos": "RB", "photo": "", "age": "25", "val": "€12M", "height": "179 cm"},
                {"name": "K. Itakura", "jersey": "4", "rating": 7.3, "pos": "RCB", "photo": "", "age": "29", "val": "€15M", "height": "186 cm"},
                {"name": "K. Machida", "jersey": "15", "rating": 7.1, "pos": "LCB", "photo": "", "age": "28", "val": "€10M", "height": "190 cm"},
                {"name": "H. Ito", "jersey": "21", "rating": 7.4, "pos": "LB", "photo": "", "age": "27", "val": "€30M", "height": "188 cm"},
                {"name": "W. Endo", "jersey": "6", "rating": 7.6, "pos": "RDM", "photo": "", "age": "33", "val": "€13M", "height": "178 cm"},
                {"name": "H. Morita", "jersey": "5", "rating": 7.5, "pos": "LDM", "photo": "", "age": "31", "val": "€15M", "height": "177 cm"},
                {"name": "R. Doan", "jersey": "8", "rating": 7.5, "pos": "RAM", "photo": "", "age": "27", "val": "€18M", "height": "172 cm"},
                {"name": "T. Minamino", "jersey": "10", "rating": 7.7, "pos": "CAM", "photo": "", "age": "31", "val": "€20M", "height": "174 cm"},
                {"name": "K. Mitoma", "jersey": "7", "rating": 8.2, "pos": "LAM", "photo": "", "age": "29", "val": "€45M", "height": "178 cm"},
                {"name": "A. Ueda", "jersey": "9", "rating": 7.3, "pos": "ST", "photo": "", "age": "27", "val": "€8M", "height": "182 cm"},
            ],
            "portugal": [
                {"name": "Diogo Costa", "jersey": "22", "rating": 7.4, "pos": "GK", "photo": "", "age": "26", "val": "€45M", "height": "186 cm"},
                {"name": "João Cancelo", "jersey": "20", "rating": 7.5, "pos": "RB", "photo": "", "age": "32", "val": "€25M", "height": "182 cm"},
                {"name": "Rúben Dias", "jersey": "4", "rating": 7.8, "pos": "RCB", "photo": "frontend/assets/dias.png", "age": "29", "val": "€80M", "height": "187 cm"},
                {"name": "Pepe", "jersey": "3", "rating": 7.2, "pos": "LCB", "photo": "", "age": "43", "val": "€1M", "height": "188 cm"},
                {"name": "Nuno Mendes", "jersey": "19", "rating": 7.6, "pos": "LB", "photo": "", "age": "23", "val": "€55M", "height": "176 cm"},
                {"name": "João Palhinha", "jersey": "6", "rating": 7.5, "pos": "RDM", "photo": "", "age": "30", "val": "€50M", "height": "190 cm"},
                {"name": "Vitinha", "jersey": "23", "rating": 7.9, "pos": "LDM", "photo": "", "age": "26", "val": "€55M", "height": "172 cm"},
                {"name": "Bernardo Silva", "jersey": "10", "rating": 8.0, "pos": "RAM", "photo": "frontend/assets/silva.png", "age": "31", "val": "€70M", "height": "173 cm"},
                {"name": "Bruno Fernandes", "jersey": "8", "rating": 8.3, "pos": "CAM", "photo": "", "age": "31", "val": "€70M", "height": "179 cm"},
                {"name": "Rafael Leão", "jersey": "17", "rating": 8.1, "pos": "LAM", "photo": "", "age": "26", "val": "€75M", "height": "188 cm"},
                {"name": "C. Ronaldo", "jersey": "7", "rating": 8.2, "pos": "ST", "photo": "", "age": "41", "val": "€15M", "height": "187 cm"},
            ],
            "argentina": [
                {"name": "G. Rulli", "jersey": "12", "rating": 6.8, "pos": "GK", "photo": "", "age": "34", "val": "€4M", "height": "189 cm", "sofa_id": "83163", "sub": False},
                {"name": "F. Medina", "jersey": "25", "rating": 6.7, "pos": "LB", "photo": "", "age": "27", "val": "€22M", "height": "184 cm", "sofa_id": "935560", "sub": False},
                {"name": "L. Martínez", "jersey": "6", "rating": 7.0, "pos": "LCB", "photo": "", "age": "28", "val": "€45M", "height": "178 cm", "sofa_id": "867205", "sub": False},
                {"name": "N. Otamendi", "jersey": "19", "rating": 7.0, "pos": "RCB", "photo": "", "age": "38", "val": "€1.5M", "height": "183 cm", "sofa_id": "47355", "sub": False},
                {"name": "A. Giay", "jersey": "28", "rating": 7.2, "pos": "RB", "photo": "", "age": "21", "val": "€8M", "height": "180 cm", "sofa_id": "1110091", "sub": False},
                {"name": "V. Barco", "jersey": "8", "rating": 7.8, "pos": "LM", "photo": "", "age": "21", "val": "€9M", "height": "172 cm", "sofa_id": "1018596", "sub": False},
                {"name": "E. Palacios", "jersey": "14", "rating": 7.0, "pos": "LCM", "photo": "", "age": "27", "val": "€40M", "height": "177 cm", "sofa_id": "831626", "sub": False},
                {"name": "G. Lo Celso", "jersey": "11", "rating": 7.0, "pos": "RCM", "photo": "", "age": "30", "val": "€16M", "height": "177 cm", "sofa_id": "349479", "sub": False},
                {"name": "G. Simeone", "jersey": "17", "rating": 6.5, "pos": "RM", "photo": "", "age": "23", "val": "€10M", "height": "180 cm", "sofa_id": "1023773", "sub": False},
                {"name": "J. López", "jersey": "21", "rating": 6.8, "pos": "LST", "photo": "", "age": "25", "val": "€15M", "height": "188 cm", "sofa_id": "1026027", "sub": False},
                {"name": "N. Paz", "jersey": "18", "rating": 6.9, "pos": "RST", "photo": "", "age": "21", "val": "€10M", "height": "186 cm", "sofa_id": "1085352", "sub": False},
                # Substitutes
                {"name": "Cristian Romero", "jersey": "13", "rating": 6.7, "pos": "RCB", "photo": "", "age": "28", "val": "€60M", "height": "185 cm", "sofa_id": "865063", "sub": True},
                {"name": "Enzo Fernández", "jersey": "24", "rating": 6.8, "pos": "CM", "photo": "", "age": "25", "val": "€75M", "height": "178 cm", "sofa_id": "966236", "sub": True},
                {"name": "Rodrigo De Paul", "jersey": "7", "rating": 7.7, "pos": "RCM", "photo": "", "age": "32", "val": "€30M", "height": "180 cm", "sofa_id": "233054", "sub": True},
                {"name": "Alexis Mac Allister", "jersey": "20", "rating": 6.9, "pos": "LCM", "photo": "", "age": "27", "val": "€75M", "height": "176 cm", "sofa_id": "868357", "sub": True},
                {"name": "Lautaro Martínez", "jersey": "22", "rating": 7.3, "pos": "ST", "photo": "", "age": "28", "val": "€110M", "height": "174 cm", "sofa_id": "830206", "sub": True},
                {"name": "Thiago Almada", "jersey": "16", "rating": 7.7, "pos": "CAM", "photo": "", "age": "25", "val": "€27M", "height": "171 cm", "sofa_id": "925345", "sub": True},
                {"name": "Nicolás González", "jersey": "15", "rating": 6.5, "pos": "LM", "photo": "", "age": "28", "val": "€35M", "height": "180 cm", "sofa_id": "828236", "sub": True},
                {"name": "Gonzalo Montiel", "jersey": "4", "rating": 6.8, "pos": "RB", "photo": "", "age": "29", "val": "€10M", "height": "175 cm", "sofa_id": "831548", "sub": True},
                {"name": "Lionel Messi", "jersey": "10", "rating": 7.7, "pos": "ST", "photo": "", "age": "38", "val": "€30M", "height": "170 cm", "sofa_id": "206", "sub": True}
            ],
            "iceland": [
                {"name": "E. Ólafsson", "jersey": "1", "rating": 6.9, "pos": "GK", "photo": "", "age": "26", "val": "€1M", "height": "201 cm", "sofa_id": "964344", "sub": False},
                {"name": "L. Tómasson", "jersey": "2", "rating": 6.6, "pos": "LB", "photo": "", "age": "27", "val": "€800K", "height": "183 cm", "sofa_id": "865769", "sub": False},
                {"name": "H. Magnússon", "jersey": "23", "rating": 6.1, "pos": "LCB", "photo": "", "age": "33", "val": "€1.2M", "height": "190 cm", "sofa_id": "117973", "sub": False},
                {"name": "D. Grétarsson", "jersey": "3", "rating": 6.1, "pos": "RCB", "photo": "", "age": "30", "val": "€500K", "height": "185 cm", "sofa_id": "263590", "sub": False},
                {"name": "V. Pálsson", "jersey": "4", "rating": 6.3, "pos": "RB", "photo": "", "age": "35", "val": "€400K", "height": "186 cm", "sofa_id": "45664", "sub": False},
                {"name": "M. Ellertsson", "jersey": "19", "rating": 6.3, "pos": "LM", "photo": "", "age": "24", "val": "€2.5M", "height": "182 cm", "sofa_id": "966456", "sub": False},
                {"name": "Í. B. Jóhannesson", "jersey": "8", "rating": 6.4, "pos": "LCM", "photo": "", "age": "23", "val": "€3.5M", "height": "180 cm", "sofa_id": "951952", "sub": False},
                {"name": "A. Baldursson", "jersey": "14", "rating": 6.4, "pos": "RCM", "photo": "", "age": "24", "val": "€800K", "height": "183 cm", "sofa_id": "926252", "sub": False},
                {"name": "A. Guðmundsson", "jersey": "11", "rating": 7.0, "pos": "RM", "photo": "", "age": "28", "val": "€22M", "height": "177 cm", "sofa_id": "826388", "sub": False},
                {"name": "H. Haraldsson", "jersey": "7", "rating": 6.4, "pos": "LST", "photo": "", "age": "23", "val": "€15M", "height": "180 cm", "sofa_id": "994468", "sub": False},
                {"name": "O. S. Óskarsson", "jersey": "9", "rating": 6.5, "pos": "RST", "photo": "", "age": "21", "val": "€5M", "height": "186 cm", "sofa_id": "1012975", "sub": False},
                # Substitutes
                {"name": "Kristian Hlynsson", "jersey": "20", "rating": 6.1, "pos": "CAM", "photo": "", "age": "22", "val": "€5M", "height": "179 cm", "sofa_id": "966453", "sub": True},
                {"name": "Dagur Dan Þórhallsson", "jersey": "15", "rating": 5.9, "pos": "LB", "photo": "", "age": "26", "val": "€1M", "height": "178 cm", "sofa_id": "926251", "sub": True},
                {"name": "Aron Gunnarsson", "jersey": "17", "rating": 6.3, "pos": "CM", "photo": "", "age": "37", "val": "€300K", "height": "177 cm", "sofa_id": "44738", "sub": True},
                {"name": "Jón Dagur Þorsteinsson", "jersey": "18", "rating": 7.0, "pos": "LM", "photo": "", "age": "27", "val": "€3M", "height": "178 cm", "sofa_id": "837269", "sub": True},
                {"name": "Hjörtur Hermannsson", "jersey": "6", "rating": 6.3, "pos": "RCB", "photo": "", "age": "30", "val": "€800K", "height": "188 cm", "sofa_id": "260021", "sub": True},
                {"name": "Gísli Þórðarson", "jersey": "5", "rating": 6.3, "pos": "RCM", "photo": "", "age": "24", "val": "€300K", "height": "180 cm", "sofa_id": "964343", "sub": True},
                {"name": "Kristall Máni Ingason", "jersey": "16", "rating": 6.4, "pos": "ST", "photo": "", "age": "24", "val": "€500K", "height": "180 cm", "sofa_id": "994467", "sub": True},
                {"name": "Arnór Sigurðsson", "jersey": "21", "rating": 6.4, "pos": "LM", "photo": "", "age": "26", "val": "€3M", "height": "177 cm", "sofa_id": "865767", "sub": True},
                {"name": "Gylfi Sigurðsson", "jersey": "10", "rating": 6.6, "pos": "CAM", "photo": "", "age": "36", "val": "€500K", "height": "186 cm", "sofa_id": "44722", "sub": True}
            ]
        }
        for k, v in roster_data.items():
            if k in name_norm:
                return v
        import hashlib
        seed = int(hashlib.md5(team_name.encode()).hexdigest(), 16)
        
        name_lower = team_name.lower()
        # Classify naming style by keyword detection
        if any(c in name_lower for c in ["spain", "peru", "colombia", "argentina", "chile", "uruguay", "paraguay", "bolivia", "ecuador", "venezuela", "mexico", "costa", "honduras", "panama", "salvador", "nicaragua", "guatemala", "cuba", "madrid", "barcelona", "sevilla", "valencia", "atletico"]):
            style = "spanish"
        elif any(c in name_lower for c in ["portugal", "brazil", "angola", "cape verde", "mozambique", "porto", "lisbon", "benfica"]):
            style = "portuguese"
        elif any(c in name_lower for c in ["germany", "austria", "swiss", "switzerland", "munich", "bayern", "dortmund", "berlin", "hamburg", "leipzig"]):
            style = "german"
        elif any(c in name_lower for c in ["italy", "milan", "inter", "juventus", "roma", "napoli", "lazio", "florence"]):
            style = "italian"
        elif any(c in name_lower for c in ["france", "haiti", "belgium", "senegal", "cameroon", "ivory", "mali", "guinea", "congo", "gabon", "paris", "marseille", "lyon"]):
            style = "french"
        elif any(c in name_lower for c in ["netherlands", "dutch", "ajax", "psv", "feyenoord"]):
            style = "dutch"
        elif any(c in name_lower for c in ["china", "japan", "korea", "vietnam", "myanmar", "thailand", "malaysia", "indonesia", "singapore", "philippines", "guam", "tokyo", "beijing", "seoul", "bangkok"]):
            style = "asian"
        elif any(c in name_lower for c in ["russia", "ukraine", "poland", "croatia", "serbia", "czech", "slovak", "bulgaria", "romania", "hungary", "albania", "greece", "turkey", "georgia", "armenia", "azerbaijan", "uzbekistan", "kazakh", "kyrgyz", "tajik", "turkmen"]):
            style = "eastern_european"
        else:
            style = "english"
            
        # Name lists
        spanish_first = ["Álvaro", "Sergio", "Ferran", "Pedro", "Dani", "Marc", "Carlos", "Luis", "Jorge", "Javier", "Andrés", "Diego", "Francisco", "Manuel", "Alejandro", "Héctor", "Santiago", "Juan", "Mateo", "Lucas"]
        spanish_last = ["García", "Rodríguez", "González", "Fernández", "López", "Martínez", "Sánchez", "Pérez", "Gómez", "Díaz", "Torres", "Ramírez", "Cruz", "Ortiz", "Flores", "Giménez", "Romero", "Alvarez", "Ruiz", "Morales"]
        
        portuguese_first = ["Cristiano", "Bernardo", "Bruno", "João", "Diogo", "Rúben", "Gonçalo", "Vítor", "António", "Pedro", "Nuno", "Lucas", "Gabriel", "Mateus", "Felipe", "Rafael", "Tiago", "André", "Duarte", "Miguel"]
        portuguese_last = ["Silva", "Santos", "Ferreira", "Pereira", "Oliveira", "Costa", "Rodrigues", "Almeida", "Nascimento", "Sousa", "Gomes", "Lopes", "Marques", "Cardoso", "Ribeiro", "Carvalho", "Teixeira", "Pinto", "Mendes", "Moreira"]
        
        german_first = ["Thomas", "Manuel", "Joshua", "Leon", "Serge", "Leroy", "Alexander", "Florian", "Lukas", "Sebastian", "Philipp", "Bastian", "Timo", "Jonas", "Julian", "Max", "Robin", "Kai", "Niklas", "Felix"]
        german_last = ["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker", "Schulz", "Hoffmann", "Schäfer", "Koch", "Bauer", "Richter", "Klein", "Wolf", "Neumann", "Schrader", "Hartmann", "Lange"]
        
        italian_first = ["Lorenzo", "Marco", "Niccolò", "Orlando", "Paolo", "Roberto", "Salvatore", "Tommaso", "Umberto", "Vincenzo", "Alessandro", "Davide", "Gianluca", "Andrea", "Federico", "Giorgio", "Matteo", "Filippo", "Francesco", "Giovanni"]
        italian_last = ["Rossi", "Bianchi", "Ferrari", "Russo", "Colombo", "Ricci", "Marino", "Greco", "Bruno", "Gallo", "Conti", "Moretti", "Mancini", "Rizzo", "Lombardi", "Giordano", "Barbieri", "Fontana", "Santoro", "Caruso"]
        
        french_first = ["Jean", "Pierre", "Frantz", "Duckens", "Wilde-Donald", "Steeven", "Carlens", "Derrick", "Louicius", "Alex", "Antoine", "Bryan", "Guerry", "Johny", "Olivier", "Hugo", "Lucas", "Nicolas", "Mathieu", "Guillaume"]
        french_last = ["Duverger", "Gérard", "Arise", "Adé", "Lacroix", "Alceus", "Joseph", "Providence", "Antoine", "Pierrot", "Nazon", "Guerrier", "Placide", "Christian", "Martin", "Bernard", "Thomas", "Petit", "Dubois", "Durand"]
        
        dutch_first = ["Virgil", "Frenkie", "Memphis", "Cody", "Nathan", "Stefan", "Denzel", "Daley", "Steven", "Georginio", "Matthijs", "Martens", "Luuk", "Justin", "Sven", "Jan", "Wouter", "Piet", "Henk", "Klaas"]
        dutch_last = ["de Jong", "van Dijk", "de Ligt", "Dumfries", "Depay", "Gakpo", "Aké", "Blind", "Wijnaldum", "Bergwijn", "de Vrij", "Janssen", "de Bakker", "Vermeer", "Klaassen", "van de Beek", "Stekelenburg", "Krul", "Cillessen", "Promes"]
        
        asian_first = ["Hiroki", "Takumi", "Wataru", "Kaoru", "Shogo", "Koki", "Daiki", "Junjie", "Lei", "Xiang", "Zhi", "Lin", "Yong", "Wei", "Bo", "Chao", "Zihan", "Min", "Kwang", "Kyung"]
        asian_last = ["Minamino", "Endo", "Mitoma", "Taniguchi", "Machida", "Wang", "Zhang", "Li", "Liu", "Chen", "Yang", "Huang", "Zhao", "Wu", "Zhou", "Xu", "Sun", "Park", "Kim", "Lee"]
        
        ee_first = ["Luka", "Mateo", "Ivan", "Domagoj", "Andrej", "Nikola", "Marcelo", "Dejan", "Josip", "Lovro", "Borislav", "Dragan", "Milan", "Stanko", "Zoran", "Sergei", "Vladimir", "Aleksandr", "Dmitry", "Alexei"]
        ee_last = ["Modric", "Kovacic", "Perisic", "Vida", "Kramaric", "Vlasic", "Brozovic", "Lovren", "Stanisic", "Majer", "Petkovic", "Orsic", "Livakovic", "Ivanusic", "Sutalo", "Smirnov", "Ivanov", "Petrov", "Sokolov", "Popov"]
        
        english_first = ["John", "James", "Robert", "William", "David", "Richard", "Joseph", "Thomas", "Charles", "Daniel", "Matthew", "Harry", "Jack", "Oliver", "George", "Charlie", "Mason", "Jude", "Declan", "Bukayo"]
        english_last = ["Smith", "Jones", "Taylor", "Brown", "Williams", "Wilson", "Johnson", "Davies", "Robinson", "Wright", "Thompson", "Evans", "Walker", "White", "Green", "Stones", "Bellingham", "Rice", "Saka", "Kane"]
        
        # Select naming lists
        if style == "spanish":
            first_list, last_list = spanish_first, spanish_last
        elif style == "portuguese":
            first_list, last_list = portuguese_first, portuguese_last
        elif style == "german":
            first_list, last_list = german_first, german_last
        elif style == "italian":
            first_list, last_list = italian_first, italian_last
        elif style == "french":
            first_list, last_list = french_first, french_last
        elif style == "dutch":
            first_list, last_list = dutch_first, dutch_last
        elif style == "asian":
            first_list, last_list = asian_first, asian_last
        elif style == "eastern_european":
            first_list, last_list = ee_first, ee_last
        else:
            first_list, last_list = english_first, english_last
            
        roster = []
        positions = ["GK", "RB", "RCB", "LCB", "LB", "LDM", "RDM", "RAM", "CAM", "LAM", "ST"]
        for i in range(11):
            p_seed = seed + i
            # Select first & last name deterministically using p_seed
            first = first_list[p_seed % len(first_list)]
            last = last_list[(p_seed * 7) % len(last_list)]
            
            p_name = f"{first[0]}. {last}"
            rating = round(6.0 + (p_seed % 30) / 10.0, 1)
            age = str(20 + (p_seed % 15))
            val = f"€{10 + (p_seed % 170)}M" if p_seed % 3 != 0 else f"€{1 + (p_seed % 10)}M"
            height = f"{170 + (p_seed % 28)} cm"
            roster.append({
                "name": p_name,
                "jersey": str((p_seed % 30) + 1),
                "rating": rating,
                "pos": positions[i],
                "photo": "",
                "age": age,
                "val": val,
                "height": height
            })
        return roster

    def get_team_nationality(team_name: str) -> str:
        name = team_name.lower()
        if "city" in name or "manchester" in name:
            return "ENG"
        elif "real" in name or "madrid" in name:
            return "ESP"
        elif "bayern" in name or "munich" in name:
            return "GER"
        elif "arsenal" in name:
            return "ENG"
        elif "haiti" in name:
            return "HTI"
        elif "new zealand" in name:
            return "NZL"
        elif "serbia" in name:
            return "SRB"
        elif "denmark" in name:
            return "DEN"
        elif "liverpool" in name:
            return "ENG"
        else:
            clean = ''.join(c for c in team_name if c.isalnum())
            return clean[:3].upper() if len(clean) >= 3 else "INT"

    # Load rosters
    home_roster = get_team_roster(home_team_name, is_home=True)
    away_roster = get_team_roster(away_team_name, is_home=False)

    # Enrich rosters with extra metrics deterministically
    def enrich_roster(roster, is_home):
        t_nat = get_team_nationality(home_team_name if is_home else away_team_name)
        for i, p in enumerate(roster):
            try:
                jersey_int = int(''.join(c for c in str(p.get("jersey", "0")) if c.isdigit()))
            except ValueError:
                jersey_int = i + 1
            p_seed = seed_val + jersey_int + (100 if not is_home else 0)
            
            # Distance
            pos = p.get("pos", "CM")
            if pos == "GK":
                dist_val = round(4.0 + (p_seed % 15) / 10.0, 1)
            elif pos in ["CM", "LCM", "RCM", "DM", "LDM", "RDM", "AM", "CAM"]:
                dist_val = round(10.5 + (p_seed % 25) / 10.0, 1)
            elif pos in ["LB", "RB", "LWB", "RWB", "LM", "RM", "LW", "RW", "LAM", "RAM"]:
                dist_val = round(9.8 + (p_seed % 20) / 10.0, 1)
            else:
                dist_val = round(8.8 + (p_seed % 20) / 10.0, 1)
            p["distance"] = f"{dist_val} km"
            
            # Nationality
            if p_seed % 6 == 0:
                mix_nats = ["BRA", "FRA", "ESP", "ARG", "GER", "POR", "BEL", "NED"]
                p["nationality"] = mix_nats[p_seed % len(mix_nats)]
            else:
                p["nationality"] = t_nat
                
            # Fantasy Points
            base_points = int(p["rating"] * 10)
            bonus = p_seed % 15
            p["fantasy"] = f"{base_points + bonus} pts"
            
            # Height fallback
            if "height" not in p:
                p["height"] = f"{175 + (p_seed % 20)} cm"
                
            # Age fallback
            if "age" not in p:
                p["age"] = str(20 + (p_seed % 15))
                
            # Value fallback
            if "val" not in p:
                p["val"] = f"€{5 + (p_seed % 95)}M"

    enrich_roster(home_roster, is_home=True)
    enrich_roster(away_roster, is_home=False)
    
    # Calculate average ratings
    home_avg = round(sum(p["rating"] for p in home_roster) / len(home_roster), 2)
    away_avg = round(sum(p["rating"] for p in away_roster) / len(away_roster), 2)
    
    # Setup team configurations & colors
    home_color = "#b91c1c"
    away_color = "#1e3a8a"
    away_text = "#fff"
    if "city" in home_team_name.lower() or "manchester" in home_team_name.lower():
        home_color = "#009bd6"
    elif "arsenal" in home_team_name.lower():
        home_color = "#ef0107"
    elif "haiti" in home_team_name.lower():
        home_color = "#0020c2"
    elif "argentina" in home_team_name.lower():
        home_color = "#75aadb"
        
    if "madrid" in away_team_name.lower():
        away_color = "#ffffff"
        away_text = "#000"
    elif "zealand" in away_team_name.lower():
        away_color = "#111827"
    elif "iceland" in away_team_name.lower():
        away_color = "#00589b"
        
    # Coords Mapping (scaled to keep all players of a team in their respective half)
    coords = {
        "GK": (5, 50),
        "LB": (15, 15),
        "LCB": (15, 38),
        "RCB": (15, 62),
        "RB": (15, 85),
        "LDM": (25, 33),
        "RDM": (25, 67),
        "LCM": (28, 25),
        "CM": (28, 50),
        "RCM": (28, 75),
        "LAM": (38, 20),
        "CAM": (38, 50),
        "RAM": (38, 80),
        "LW": (44, 15),
        "ST": (45, 50),
        "RW": (44, 85),
        "LST": (45, 33),
        "RST": (45, 67),
        "LM": (32, 15),
        "RM": (32, 85),
        "AM": (38, 50)
    }
    
    # Interactive display controls using segmented_control for premium visual styling
    st.markdown("##### ⚙️ Roster Display Controls")
    col_toggle, col_filter = st.columns([1, 2])
    with col_toggle:
        lineup_mode = st.segmented_control(
            "Display Mode:", 
            options=["Lineups", "Player Stats"], 
            default="Lineups", 
            label_visibility="collapsed"
        )
    with col_filter:
        metric_filter = st.segmented_control(
            "Overlay Metric:", 
            options=["Performance", "Distance", "Nationality", "Age", "Market Value", "Fantasy"], 
            default="Performance", 
            label_visibility="collapsed"
        )
    st.markdown("")

    # custom styling override for segmented control buttons to match the vibrant green active pill state in SofaScore
    st.html(f"""
    <style>
    div[data-testid="stSegmentedControl"] button[aria-checked="true"] {{
        background-color: #10b981 !important;
        color: #000000 !important;
        font-weight: 800 !important;
    }}
    div[data-testid="stSegmentedControl"] button {{
        border-radius: 9999px !important;
        font-family: "Space Grotesk", sans-serif !important;
    }}
    </style>
    <div style="background-color: #0c1210; border: 1px solid #142820; border-radius: 0.75rem; padding: 1.2rem; margin-bottom: 1rem;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-weight: 700; color: #f3f4f6; font-size: 1.1rem;">{home_team_name}</span>
                <span style="background-color: #10b981; color: #000; font-size: 0.85rem; font-weight: 800; padding: 0.15rem 0.4rem; border-radius: 0.25rem;">{home_avg}</span>
            </div>
            <div style="display: flex; flex-direction: column; align-items: center; font-size: 0.75rem; color: #6b7280;">
                <span style="font-weight: 700; color: #9ca3af;">{metric_filter} Overlay</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="background-color: #10b981; color: #000; font-size: 0.85rem; font-weight: 800; padding: 0.15rem 0.4rem; border-radius: 0.25rem;">{away_avg}</span>
                <span style="font-weight: 700; color: #f3f4f6; font-size: 1.1rem;">{away_team_name}</span>
            </div>
        </div>
    </div>
    """)

    if lineup_mode == "Lineups":
        # Resolve SofaScore Match ID
        SOFASCORE_MATCH_IDS = {
            "peru-spain": "16123045",
            "spain-peru": "16123045",
            "manchester city-real madrid": "12228399",
            "real madrid-manchester city": "12228399",
            "arsenal-bayern munich": "12228397",
            "bayern munich-arsenal": "12228397",
            "liverpool-manchester city": "11980838",
            "manchester city-liverpool": "11980838",
            "haiti-new zealand": "11352345",
            "new zealand-haiti": "11352345",
            "philippines-guam": "11352346",
            "guam-philippines": "11352346",
            "japan-portugal": "11352347",
            "portugal-japan": "11352347",
            "argentina-iceland": "11352348",
            "iceland-argentina": "11352348"
        }
        
        home_norm = home_team_name.lower().strip()
        away_norm = away_team_name.lower().strip()
        sofa_match_id = None
        for k, v in SOFASCORE_MATCH_IDS.items():
            k_parts = k.split("-")
            if (k_parts[0] in home_norm and k_parts[1] in away_norm) or (k_parts[0] in away_norm and k_parts[1] in home_norm):
                sofa_match_id = v
                break
                
        if sofa_match_id:
            st.markdown("##### 🎨 Visual Style Selector")
            pitch_style = st.segmented_control(
                "Pitch Visual Style:",
                options=["2D Tactical Board", "Official SofaScore Widget"],
                default="Official SofaScore Widget",
                label_visibility="collapsed"
            )
            st.markdown("")
        else:
            pitch_style = "2D Tactical Board"
            
        if pitch_style == "Official SofaScore Widget":
            st.html(f"""
            <div style="display: flex; justify-content: center; margin-top: 1rem; width: 100%;">
                <iframe id="sofa-lineups-embed-{sofa_match_id}" 
                        src="https://widgets.sofascore.com/embed/lineups?id={sofa_match_id}&widgetTheme=dark" 
                        style="height: 786px !important; max-width: 800px !important; width: 100% !important; border: none; border-radius: 0.75rem;" 
                        frameborder="0" 
                        scrolling="no"
                        referrerpolicy="no-referrer">
                </iframe>
            </div>
            """)
        else:
            # Generate player tags
            players_html = ""
            
            # Home Team placement
            for p in home_roster:
                if p.get("sub", False):
                    continue
                pos = p["pos"]
                x, y = coords.get(pos, (50, 50))
                left_pct = x
                top_pct = y
                
                rating = p["rating"]
                
                # Setup dynamic metric values inside the badges
                if metric_filter == "Performance":
                    badge_text = str(rating)
                    if rating >= 8.0:
                        badge_bg = "#10b981"
                        badge_fg = "#000"
                    elif rating >= 7.0:
                        badge_bg = "#34d399"
                        badge_fg = "#000"
                    elif rating >= 6.0:
                        badge_bg = "#f59e0b"
                        badge_fg = "#000"
                    else:
                        badge_bg = "#ef4444"
                        badge_fg = "#fff"
                elif metric_filter == "Age":
                    badge_text = p["age"] + " yrs"
                    badge_bg = "#374151"
                    badge_fg = "#fff"
                elif metric_filter == "Market Value":
                    badge_text = p["val"]
                    badge_bg = "#047857"
                    badge_fg = "#fff"
                elif metric_filter == "Distance":
                    badge_text = p["distance"]
                    badge_bg = "#3b82f6"
                    badge_fg = "#fff"
                elif metric_filter == "Nationality":
                    badge_text = p["nationality"]
                    badge_bg = "#8b5cf6"
                    badge_fg = "#fff"
                elif metric_filter == "Fantasy":
                    badge_text = p["fantasy"]
                    badge_bg = "#ec4899"
                    badge_fg = "#fff"
                else:
                    badge_text = p.get("height", "180 cm")
                    badge_bg = "#4b5563"
                    badge_fg = "#fff"
                    
                img_src = get_image_base64(p.get("photo", ""))
                if img_src:
                    circle_content = f'<img src="{img_src}" style="width:100%; height:100%; object-fit:cover;" />'
                else:
                    circle_content = f'<div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center; background-color:{home_color}; color:#fff; font-weight:800; font-size:0.85rem;">{p["jersey"]}</div>'
                    
                players_html += f"""
                <div class="player-node" style="left: {left_pct}%; top: {top_pct}%;">
                    <div class="player-circle">{circle_content}</div>
                    <div class="rating-badge" style="background-color: {badge_bg}; color: {badge_fg};">{badge_text}</div>
                    <div class="player-name-label">{p["name"]}</div>
                    <div class="player-jersey-label">#{p["jersey"]}</div>
                </div>
                """
                
            # Away Team placement
            for p in away_roster:
                if p.get("sub", False):
                    continue
                pos = p["pos"]
                x, y = coords.get(pos, (50, 50))
                left_pct = 100 - x
                top_pct = y
                
                rating = p["rating"]
                
                # Setup dynamic metric values inside the badges
                if metric_filter == "Performance":
                    badge_text = str(rating)
                    if rating >= 8.0:
                        badge_bg = "#10b981"
                        badge_fg = "#000"
                    elif rating >= 7.0:
                        badge_bg = "#34d399"
                        badge_fg = "#000"
                    elif rating >= 6.0:
                        badge_bg = "#f59e0b"
                        badge_fg = "#000"
                    else:
                        badge_bg = "#ef4444"
                        badge_fg = "#fff"
                elif metric_filter == "Age":
                    badge_text = p["age"] + " yrs"
                    badge_bg = "#374151"
                    badge_fg = "#fff"
                elif metric_filter == "Market Value":
                    badge_text = p["val"]
                    badge_bg = "#047857"
                    badge_fg = "#fff"
                elif metric_filter == "Distance":
                    badge_text = p["distance"]
                    badge_bg = "#3b82f6"
                    badge_fg = "#fff"
                elif metric_filter == "Nationality":
                    badge_text = p["nationality"]
                    badge_bg = "#8b5cf6"
                    badge_fg = "#fff"
                elif metric_filter == "Fantasy":
                    badge_text = p["fantasy"]
                    badge_bg = "#ec4899"
                    badge_fg = "#fff"
                else:
                    badge_text = p.get("height", "180 cm")
                    badge_bg = "#4b5563"
                    badge_fg = "#fff"
                    
                img_src = get_image_base64(p.get("photo", ""))
                if img_src:
                    circle_content = f'<img src="{img_src}" style="width:100%; height:100%; object-fit:cover;" />'
                else:
                    circle_content = f'<div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center; background-color:{away_color}; color:{away_text}; font-weight:800; font-size:0.85rem;">{p["jersey"]}</div>'
                    
                players_html += f"""
                <div class="player-node" style="left: {left_pct}%; top: {top_pct}%;">
                    <div class="player-circle">{circle_content}</div>
                    <div class="rating-badge" style="background-color: {badge_bg}; color: {badge_fg};">{badge_text}</div>
                    <div class="player-name-label">{p["name"]}</div>
                    <div class="player-jersey-label">#{p["jersey"]}</div>
                </div>
                """
                
            # Draw full pitch board using st.html to prevent any markdown preformatted / code block parsing errors
            st.html(f"""
            <style>
            .pitch-board {{
                position: relative;
                width: 100%;
                height: 520px;
                background-color: #0c1c12;
                border: 2px solid #1a3c25;
                border-radius: 0.75rem;
                overflow: hidden;
                margin-bottom: 2rem;
                box-shadow: inset 0 0 50px rgba(0,0,0,0.8);
            }}
            .pitch-line-center {{
                position: absolute;
                left: 50%;
                top: 0;
                bottom: 0;
                width: 2px;
                background-color: rgba(255,255,255,0.12);
            }}
            .pitch-line-circle {{
                position: absolute;
                left: 50%;
                top: 50%;
                width: 110px;
                height: 110px;
                border: 2px solid rgba(255,255,255,0.12);
                border-radius: 50%;
                transform: translate(-50%, -50%);
            }}
            .pitch-line-center-dot {{
                position: absolute;
                left: 50%;
                top: 50%;
                width: 6px;
                height: 6px;
                background-color: rgba(255,255,255,0.15);
                border-radius: 50%;
                transform: translate(-50%, -50%);
            }}
            .pitch-penalty-left {{
                position: absolute;
                left: 0;
                top: 22%;
                width: 75px;
                height: 56%;
                border: 2px solid rgba(255,255,255,0.12);
                border-left: none;
            }}
            .pitch-penalty-left-inner {{
                position: absolute;
                left: 0;
                top: 36%;
                width: 25px;
                height: 28%;
                border: 2px solid rgba(255,255,255,0.12);
                border-left: none;
            }}
            .pitch-penalty-right {{
                position: absolute;
                right: 0;
                top: 22%;
                width: 75px;
                height: 56%;
                border: 2px solid rgba(255,255,255,0.12);
                border-right: none;
            }}
            .pitch-penalty-right-inner {{
                position: absolute;
                right: 0;
                top: 36%;
                width: 25px;
                height: 28%;
                border: 2px solid rgba(255,255,255,0.12);
                border-right: none;
            }}
            .player-node {{
                position: absolute;
                transform: translate(-50%, -50%);
                display: flex;
                flex-direction: column;
                align-items: center;
                width: 75px;
                transition: transform 0.2s ease;
            }}
            .player-node:hover {{
                transform: translate(-50%, -50%) scale(1.1);
                z-index: 100;
            }}
            .player-circle {{
                width: 44px;
                height: 44px;
                border-radius: 50%;
                border: 2px solid #ffffff;
                background-color: #1a2c22;
                box-shadow: 0 4px 10px rgba(0,0,0,0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
            }}
            .rating-badge {{
                font-size: 0.65rem;
                font-weight: 800;
                padding: 0.1rem 0.35rem;
                border-radius: 0.25rem;
                margin-top: -8px;
                z-index: 10;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                border: 1px solid rgba(0,0,0,0.2);
            }}
            .player-name-label {{
                color: #f3f4f6;
                font-size: 0.68rem;
                font-weight: 700;
                text-align: center;
                margin-top: 4px;
                white-space: nowrap;
                text-shadow: 0 1px 3px rgba(0,0,0,0.9), 0 0 5px rgba(0,0,0,0.5);
            }}
            .player-jersey-label {{
                color: #9ca3af;
                font-size: 0.62rem;
                font-weight: 600;
                margin-top: 1px;
                text-shadow: 0 1px 3px rgba(0,0,0,0.9);
            }}
            </style>
            <div class="pitch-board">
                <div class="pitch-line-center"></div>
                <div class="pitch-line-circle"></div>
                <div class="pitch-line-center-dot"></div>
                <div class="pitch-penalty-left"></div>
                <div class="pitch-penalty-left-inner"></div>
                <div class="pitch-penalty-right"></div>
                <div class="pitch-penalty-right-inner"></div>
                {players_html}
            </div>
            """)
    else:
        st.markdown("#### 📊 Roster Statistical Breakdown")
        
        # Build table rows
        rows_html = ""
        # Home roster rows - Starters
        rows_html += f"""<tr style="background-color: #0c1814;"><td colspan="10" style="padding: 0.5rem; color: #10b981; font-weight: 800; text-align: left; border-bottom: 1px solid #142820; font-family: 'Space Grotesk';">{home_team_name} - STARTING XI</td></tr>"""
        for p in home_roster:
            if p.get("sub", False):
                continue
            rows_html += f"""
            <tr>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #f3f4f6; font-weight:600;">{p['name']}</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #10b981;">{home_team_name}</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #9ca3af; font-family:monospace;">{p['pos']}</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; font-weight:700; color:#10b981;">{p['rating']}</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #f3f4f6;">{p['nationality']}</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #9ca3af;">{p['age']} yrs</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #34d399;">{p['val']}</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #9ca3af;">{p['height']}</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #3b82f6;">{p['distance']}</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #ec4899;">{p['fantasy']}</td>
            </tr>
            """
        # Home roster rows - Substitutes
        home_subs = [p for p in home_roster if p.get("sub", False)]
        if home_subs:
            rows_html += f"""<tr style="background-color: #0c1814;"><td colspan="10" style="padding: 0.5rem; color: #e5e7eb; font-weight: 800; text-align: left; border-bottom: 1px solid #142820; font-family: 'Space Grotesk';">{home_team_name} - SUBSTITUTES</td></tr>"""
            for p in home_subs:
                rows_html += f"""
                <tr>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #f3f4f6; font-weight:600;">{p['name']}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #10b981;">{home_team_name}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #9ca3af; font-family:monospace;">{p['pos']}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; font-weight:700; color:#10b981;">{p['rating']}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #f3f4f6;">{p['nationality']}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #9ca3af;">{p['age']} yrs</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #34d399;">{p['val']}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #9ca3af;">{p['height']}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #3b82f6;">{p['distance']}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #ec4899;">{p['fantasy']}</td>
                </tr>
                """
        # Away roster rows - Starters
        rows_html += f"""<tr style="background-color: #0c1814;"><td colspan="10" style="padding: 0.5rem; color: #3b82f6; font-weight: 800; text-align: left; border-bottom: 1px solid #142820; font-family: 'Space Grotesk';">{away_team_name} - STARTING XI</td></tr>"""
        for p in away_roster:
            if p.get("sub", False):
                continue
            rows_html += f"""
            <tr>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #f3f4f6; font-weight:600;">{p['name']}</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #3b82f6;">{away_team_name}</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #9ca3af; font-family:monospace;">{p['pos']}</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; font-weight:700; color:#10b981;">{p['rating']}</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #f3f4f6;">{p['nationality']}</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #9ca3af;">{p['age']} yrs</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #34d399;">{p['val']}</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #9ca3af;">{p['height']}</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #3b82f6;">{p['distance']}</td>
                <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #ec4899;">{p['fantasy']}</td>
            </tr>
            """
        # Away roster rows - Substitutes
        away_subs = [p for p in away_roster if p.get("sub", False)]
        if away_subs:
            rows_html += f"""<tr style="background-color: #0c1814;"><td colspan="10" style="padding: 0.5rem; color: #e5e7eb; font-weight: 800; text-align: left; border-bottom: 1px solid #142820; font-family: 'Space Grotesk';">{away_team_name} - SUBSTITUTES</td></tr>"""
            for p in away_subs:
                rows_html += f"""
                <tr>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #f3f4f6; font-weight:600;">{p['name']}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #3b82f6;">{away_team_name}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #9ca3af; font-family:monospace;">{p['pos']}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; font-weight:700; color:#10b981;">{p['rating']}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #f3f4f6;">{p['nationality']}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #9ca3af;">{p['age']} yrs</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #34d399;">{p['val']}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #9ca3af;">{p['height']}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #3b82f6;">{p['distance']}</td>
                    <td style="padding: 0.5rem; border-bottom: 1px solid #142820; color: #ec4899;">{p['fantasy']}</td>
                </tr>
                """
            
        st.html(f"""
        <table style="width: 100%; border-collapse: collapse; background-color: #0c1210; border: 1px solid #142820; border-radius: 0.75rem; overflow: hidden; font-size: 0.85rem;">
            <thead>
                <tr style="background-color: #10b981; color: #000; font-weight:800; text-align:left;">
                    <th style="padding: 0.6rem;">Player</th>
                    <th style="padding: 0.6rem;">Team</th>
                    <th style="padding: 0.6rem;">Position</th>
                    <th style="padding: 0.6rem;">Rating</th>
                    <th style="padding: 0.6rem;">Nationality</th>
                    <th style="padding: 0.6rem;">Age</th>
                    <th style="padding: 0.6rem;">Market Value</th>
                    <th style="padding: 0.6rem;">Height</th>
                    <th style="padding: 0.6rem;">Distance</th>
                    <th style="padding: 0.6rem;">Fantasy</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        """)
    
    st.markdown("---")
    
    st.markdown("### 👤 SofaScore Positional Rating & Heatmap Index")
    st.markdown("Select any active player from your customized formation to view their performance ratings and intensity zones.")
    
    col_pctrl, col_pheat = st.columns([1, 1])
    
    # 2. Dynamic Player Roster options from both teams
    player_options = []
    for p in home_roster:
        player_options.append(f"🏠 {home_team_name}: {p['name']} ({p['pos']} #{p['jersey']})")
    for p in away_roster:
        player_options.append(f"✈️ {away_team_name}: {p['name']} ({p['pos']} #{p['jersey']})")
        
    if not player_options:
        player_options = ["No active players"]
        
    with col_pctrl:
        selected_player = st.selectbox("Select Player Slot:", options=player_options)
        
        # Find player details
        selected_p_obj = None
        p_is_home = True
        for p in home_roster:
            opt = f"🏠 {home_team_name}: {p['name']} ({p['pos']} #{p['jersey']})"
            if opt == selected_player:
                selected_p_obj = p
                p_is_home = True
                break
        if not selected_p_obj:
            for p in away_roster:
                opt = f"✈️ {away_team_name}: {p['name']} ({p['pos']} #{p['jersey']})"
                if opt == selected_player:
                    selected_p_obj = p
                    p_is_home = False
                    break
                    
        # Fallback in case no match
        if not selected_p_obj and home_roster:
            selected_p_obj = home_roster[0]
            p_is_home = True
            
        if selected_p_obj:
            pos = selected_p_obj["pos"]
            rating = selected_p_obj["rating"]
            p_name = selected_p_obj["name"]
            p_team = home_team_name if p_is_home else away_team_name
            p_nat = selected_p_obj.get("nationality", "INT")
            p_age = selected_p_obj.get("age", "25")
            p_height = selected_p_obj.get("height", "180 cm")
            p_jersey = f"#{selected_p_obj['jersey']}"
            p_val = selected_p_obj.get("val", "€20M")
            
            # Deterministic traits, foot, weight, and attribute scores from name hash
            import hashlib
            p_hash = int(hashlib.md5(p_name.encode()).hexdigest(), 16)
            offset = p_hash % 15
            p_foot = "Right" if p_hash % 3 != 0 else "Left"
            p_weight = f"{70 + (p_hash % 20)} kg"
            
            # Traits map
            traits_map = {
                "GK": "Sweeper-keeper & pin-point distributor",
                "LB": "Overlapping fullback & defensive anchor",
                "RB": "Overlapping fullback & defensive anchor",
                "LCB": "Commanding stopper & backline leader",
                "RCB": "Commanding stopper & backline leader",
                "LDM": "Tactical pivot & rest-defense blocker",
                "RDM": "Tactical pivot & rest-defense blocker",
                "LCM": "Box-to-box transition engine",
                "CM": "Box-to-box transition engine",
                "RCM": "Box-to-box transition engine",
                "LAM": "Creative playmaker & half-space facilitator",
                "CAM": "Creative playmaker & half-space facilitator",
                "RAM": "Creative playmaker & half-space facilitator",
                "AM": "Creative playmaker & half-space facilitator",
                "LW": "Dynamic touchline speedster & inside cutter",
                "RW": "Dynamic touchline speedster & inside cutter",
                "ST": "Acrobatic target man & clinical finisher",
                "LST": "Acrobatic target man & clinical finisher",
                "RST": "Acrobatic target man & clinical finisher",
                "LM": "Hard-working wide transition midfielder",
                "RM": "Hard-working wide transition midfielder"
            }
            p_trait = traits_map.get(pos, "Versatile tactical contributor")
            
            # Generate attribute scores based on position
            base_val = int(rating * 10)
            if pos == "GK":
                phy = int(base_val * 0.9) + (offset % 10)
                cre = 30 + (offset % 20)
                dfn = int(base_val * 1.1) + (offset % 5)
                tec = 50 + (offset % 15)
                tac = int(base_val * 1.0) + (offset % 10)
                att = 10 + (offset % 10)
            elif pos in ["RCB", "LCB", "LB", "RB"]:
                phy = int(base_val * 1.05) + (offset % 8)
                cre = 40 + (offset % 20)
                dfn = int(base_val * 1.1) + (offset % 5)
                tec = 60 + (offset % 15)
                tac = int(base_val * 1.0) + (offset % 10)
                att = 30 + (offset % 15)
            elif pos in ["LDM", "RDM", "CM", "LCM", "RCM", "LM", "RM"]:
                phy = int(base_val * 0.95) + (offset % 10)
                cre = int(base_val * 1.0) + (offset % 8)
                dfn = int(base_val * 0.9) + (offset % 10)
                tec = int(base_val * 1.0) + (offset % 5)
                tac = int(base_val * 1.05) + (offset % 5)
                att = 55 + (offset % 15)
            elif pos in ["CAM", "LAM", "RAM", "AM", "LW", "RW"]:
                phy = 70 + (offset % 10)
                cre = int(base_val * 1.1) + (offset % 5)
                dfn = 35 + (offset % 15)
                tec = int(base_val * 1.1) + (offset % 5)
                tac = int(base_val * 0.95) + (offset % 10)
                att = int(base_val * 1.0) + (offset % 8)
            else: # ST, LST, RST
                phy = int(base_val * 1.0) + (offset % 10)
                cre = 65 + (offset % 15)
                dfn = 25 + (offset % 15)
                tec = int(base_val * 1.0) + (offset % 10)
                tac = int(base_val * 0.95) + (offset % 10)
                att = int(base_val * 1.15) + (offset % 5)
                
            phy = max(10, min(99, phy))
            cre = max(10, min(99, cre))
            dfn = max(10, min(99, dfn))
            tec = max(10, min(99, tec))
            tac = max(10, min(99, tac))
            att = max(10, min(99, att))
            
            # Rating badge color
            if rating >= 8.0:
                rating_color = "#10b981"
            elif rating >= 7.0:
                rating_color = "#34d399"
            elif rating >= 6.0:
                rating_color = "#f59e0b"
            else:
                rating_color = "#ef4444"
                
            # Resolve player photo
            avatar_path = selected_p_obj.get("photo", "")
            import os
            if not avatar_path or not os.path.exists(avatar_path):
                if pos == "GK":
                    avatar_path = "frontend/assets/goalkeeper_avatar.svg"
                elif pos in ["LB", "LCB", "RCB", "RB"]:
                    avatar_path = "frontend/assets/defender_avatar.svg"
                elif pos in ["LDM", "RDM", "LCM", "CM", "RCM", "LM", "RM", "LAM", "CAM", "RAM", "AM"]:
                    avatar_path = "frontend/assets/midfielder_avatar.svg"
                elif pos in ["LW", "RW", "ST", "LST", "RST"]:
                    avatar_path = "frontend/assets/striker_avatar.svg"
                else:
                    avatar_path = "frontend/assets/default_avatar.svg"
        else:
            # Absolute fallback values
            rating, rating_color = 7.0, "#34d399"
            phy = cre = dfn = tec = tac = att = 70
            p_name = "Unknown Player"
            p_jersey = "#0"
            p_age = "25"
            p_nat = "INT"
            p_foot = "Right"
            p_height = "180 cm"
            p_weight = "75 kg"
            p_val = "€1M"
            p_trait = "Tactical option"
            avatar_path = "frontend/assets/default_avatar.svg"
            pos = "CM"

        # Create a side-by-side row for the Player Avatar Card and the SofaScore rating card
        col_avatar, col_rating = st.columns([1.1, 1.0])
        with col_avatar:
            st.image(avatar_path, use_container_width=True)
            
        with col_rating:
            st.markdown(f"""
            <div style="background-color: #0c1210; border: 1px solid #142820; border-radius: 0.75rem; padding: 1.2rem; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 200px; margin-bottom: 1.2rem; height: 90%;">
                <div style="text-align: center; margin-bottom: 1rem;">
                    <h4 style="margin: 0; color: #f3f4f6; font-size: 1.05rem; font-family: 'Space Grotesk';">SofaScore Rating</h4>
                    <p style="margin: 0.2rem 0 0 0; color: #6b7280; font-size: 0.8rem;">Matchday Telemetry</p>
                </div>
                <div style="background-color: {rating_color}; color: #000; font-size: 2.5rem; font-weight: 800; padding: 0.6rem 1.5rem; border-radius: 0.5rem; text-align: center; box-shadow: 0 4px 15px rgba(16, 185, 129, 0.2);">
                    {rating}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        # Detailed Player Bio Profile Card
        st.markdown(f"""
        <div style="background-color: #0c1210; border: 1px solid #142820; border-radius: 0.75rem; padding: 1.2rem; margin-bottom: 1.2rem;">
            <h5 style="color: #34d399; font-family: 'Space Grotesk'; margin: 0 0 0.8rem 0;">👤 ACCURATE PLAYER PROFILE</h5>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem; font-size: 0.85rem; color: #9ca3af;">
                <div><b>Full Name:</b> <span style="color:#f3f4f6;">{p_name}</span></div>
                <div><b>Jersey Number:</b> <span style="color:#f3f4f6;">{p_jersey}</span></div>
                <div><b>Age / Nationality:</b> <span style="color:#f3f4f6;">{p_age} yrs / {p_nat}</span></div>
                <div><b>Preferred Foot:</b> <span style="color:#f3f4f6;">{p_foot}</span></div>
                <div><b>Height / Weight:</b> <span style="color:#f3f4f6;">{p_height} / {p_weight}</span></div>
                <div><b>Market Value:</b> <span style="color:#10b981; font-weight:600;">{p_val}</span></div>
                <div style="grid-column: span 2;"><b>Key Playstyle Trait:</b> <span style="color:#34d399; font-style:italic;">{p_trait}</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Helper to generate the Radar Hexagon Chart SVG
        def draw_attribute_hexagon(att: int, tec: int, cre: int, phy: int, tac: int, dfn: int) -> str:
            cx, cy = 110, 110
            R = 75  # radius adjusted to keep labels safe from clipping
            
            import math
            # 6 angles for a regular hexagon: ATT, TEC, CRE, PHY, TAC, DEF
            # Starting at -90 degrees (pointing straight up)
            angles = [-math.pi/2, -math.pi/6, math.pi/6, math.pi/2, 5*math.pi/6, 7*math.pi/6]
            
            def get_coords(r_val, angle):
                return cx + r_val * math.cos(angle), cy + r_val * math.sin(angle)
                
            # Grid polygons (concentric hexagons at 25%, 50%, 75%, 100%)
            grid_lines = []
            for pct in [0.25, 0.50, 0.75, 1.0]:
                r_curr = R * pct
                pts = [get_coords(r_curr, a) for a in angles]
                pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
                grid_lines.append(f'<polygon points="{pts_str}" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="1"/>')
                
            # Axis diagonal lines from center to outer corners
            axis_paths = []
            outer_pts = [get_coords(R, a) for a in angles]
            for ox, oy in outer_pts:
                axis_paths.append(f'<line x1="{cx}" y1="{cy}" x2="{ox:.1f}" y2="{oy:.1f}" stroke="rgba(255,255,255,0.1)" stroke-width="1"/>')
                
            # Player polygon coordinates based on values
            vals = [att, tec, cre, phy, tac, dfn]
            ply_pts = []
            for val, angle in zip(vals, angles):
                r_curr = R * (val / 100.0)
                ply_pts.append(get_coords(r_curr, angle))
            ply_pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in ply_pts)
            
            # Draw semi-transparent filled polygon and main stroke outline
            player_polygon = f'<polygon points="{ply_pts_str}" fill="rgba(16, 185, 129, 0.2)" stroke="#10b981" stroke-width="2"/>'
            
            # Vertex circle dots
            vertex_dots = []
            for px, py in ply_pts:
                vertex_dots.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="#10b981" stroke="#ffffff" stroke-width="0.75"/>')
                
            # Labels placed outside vertices
            labels = ["ATT", "TEC", "CRE", "PHY", "TAC", "DEF"]
            label_elems = []
            for label, angle in zip(labels, angles):
                lx, ly = get_coords(R + 14, angle)
                
                # Determine text alignment anchor based on horizontal angle position
                if math.cos(angle) > 0.1:
                    text_anchor = "start"
                elif math.cos(angle) < -0.1:
                    text_anchor = "end"
                else:
                    text_anchor = "middle"
                    
                # Adjust vertical baseline offset
                if math.sin(angle) > 0.1:
                    dy = "0.75em"
                elif math.sin(angle) < -0.1:
                    dy = "-0.2em"
                else:
                    dy = "0.35em"
                    
                label_elems.append(
                    f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{text_anchor}" dy="{dy}" '
                    f'fill="#9ca3af" font-size="9" font-weight="700" font-family="\'Space Grotesk\', sans-serif">{label}</text>'
                )
                
            svg_code = f"""
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 220" width="100%" height="auto" style="max-width: 170px; display: block; margin: auto;">
              <!-- Concentric Grid -->
              {"".join(grid_lines)}
              {"".join(axis_paths)}
              <!-- Radar Area -->
              {player_polygon}
              {"".join(vertex_dots)}
              <!-- Axis Labels -->
              {"".join(label_elems)}
            </svg>
            """
            return svg_code

        st.markdown("##### 🎭 Playstyle Attribute Hexagon Profile")
        
        # Split attributes and Hexagon side-by-side using columns
        col_attr_list, col_attr_hex = st.columns([1.2, 0.8])
        
        with col_attr_list:
            def render_attribute(label: str, pct: int):
                filled = "█" * (pct // 10)
                empty = "░" * (10 - len(filled))
                st.markdown(f"""
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.35rem; font-size: 0.8rem;">
                    <span style="color: #9ca3af;">{label}</span>
                    <span style="font-family: monospace; color: #34d399;">{filled}{empty} {pct}%</span>
                </div>
                """, unsafe_allow_html=True)
                
            render_attribute("🚀 Attacking & Finishing", att)
            render_attribute("🎛️ Technical & Control", tec)
            render_attribute("🪄 Creativity & Key Passes", cre)
            render_attribute("🏃‍♂️ Physicality & Workrate", phy)
            render_attribute("🧠 Tactical Scanning & Def", tac)
            render_attribute("🛡️ Defending & Swarming", dfn)
            
        with col_attr_hex:
            hexagon_svg = draw_attribute_hexagon(att, tec, cre, phy, tac, dfn)
            st.markdown(clean_html(hexagon_svg), unsafe_allow_html=True)
        
    # Helper functions for the Graphical Heatmap
    def generate_graphical_heatmap(pos: str, player_name: str, sofa_id: str) -> str:
        # Deterministic random generator based on player metadata
        seed = sum(ord(c) for c in player_name) + int(sofa_id or 0)
        import random
        rng = random.Random(seed)
        
        # Base layout configurations (scaled to viewBox 500x320)
        layouts = {}
        
        # Forward / Strikers (Attack final third central, heavy box presence)
        layouts["ST"] = [
            (430, 160, 1.2), # Main box presence
            (405, 140, 0.9), # Left channel box
            (410, 185, 0.9), # Right channel box
            (370, 160, 1.0), # Edge of the box / central channel
            (330, 150, 0.7), # Drop down link-up
            (445, 160, 0.7), # Near goal face
        ]
        
        # Left Wingers (High left flank, cut inside opponent box)
        layouts["LW"] = [
            (420, 60, 1.1),  # Inside left of penalty area
            (380, 50, 1.0),  # Left wing final third
            (440, 70, 0.9),  # Byline left crossing zone
            (320, 55, 0.8),  # Midfield progression left
            (260, 65, 0.7),  # Halfway line left transition
            (410, 110, 0.6), # Cut inside central shot zone
        ]
        
        # Right Wingers (High right flank, cut inside opponent box)
        layouts["RW"] = [
            (420, 260, 1.1), # Inside right of penalty area
            (380, 270, 1.0), # Right wing final third
            (440, 250, 0.9), # Byline right crossing zone
            (320, 265, 0.8), # Midfield progression right
            (260, 255, 0.7), # Halfway line right transition
            (410, 210, 0.6), # Cut inside central shot zone
        ]
        
        # Attacking Midfielders (Final third central channels, support wings)
        layouts["CAM"] = [
            (350, 160, 1.2), # Main CAM pocket
            (380, 120, 0.8), # Left half-space support
            (380, 200, 0.8), # Right half-space support
            (310, 160, 1.0), # Midfield distribution zone
            (270, 150, 0.7), # Deep central transition
            (415, 160, 0.6), # Box entrance link up
        ]
        
        # Central Midfielders (Box-to-box, extensive coverage)
        layouts["CM"] = [
            (280, 160, 1.3), # Central engine zone
            (320, 130, 0.9), # Attacking midfield left
            (320, 190, 0.9), # Attacking midfield right
            (240, 140, 0.8), # Defensive midfield cover left
            (240, 180, 0.8), # Defensive midfield cover right
            (360, 160, 0.6), # Box edge drop off
            (190, 160, 0.5), # Back support cover
        ]
        
        # Defensive Midfielders (Pivot, central defensive third cover)
        layouts["DM"] = [
            (220, 160, 1.3), # Pivot zone center
            (200, 120, 0.9), # Left pivot coverage
            (200, 200, 0.9), # Right pivot coverage
            (260, 160, 1.0), # Forward pressing transition
            (170, 160, 0.7), # Deep backline shield
            (250, 110, 0.5), # Left flank cover
            (250, 210, 0.5), # Right flank cover
        ]
        
        # Left Backs (Flank defense and wide overlapping runs)
        layouts["LB"] = [
            (160, 50, 1.2),  # Main left back defensive zone
            (230, 45, 1.0),  # Left flank midfield transition
            (110, 55, 0.9),  # Deep left defensive cover
            (300, 40, 0.8),  # Midfield-attacking third transition
            (360, 45, 0.7),  # High overlapping cross zone
            (180, 100, 0.6), # Central recovery assistance
        ]
        
        # Right Backs (Flank defense and wide overlapping runs)
        layouts["RB"] = [
            (160, 270, 1.2), # Main right back defensive zone
            (230, 275, 1.0), # Right flank midfield transition
            (110, 265, 0.9), # Deep right defensive cover
            (300, 280, 0.8), # Midfield-attacking third transition
            (360, 275, 0.7), # High overlapping cross zone
            (180, 220, 0.6), # Central recovery assistance
        ]
        
        # Center Backs (Defensive third block, penalty box protection)
        layouts["CB"] = [
            (120, 160, 1.3), # Heart of own box
            (140, 115, 0.9), # Left center back channel
            (140, 205, 0.9), # Right center back channel
            (85, 160, 0.8),  # Six yard box recovery
            (175, 160, 0.9), # Top of penalty box cover
            (190, 120, 0.5), # High line left cover
            (190, 200, 0.5), # High line right cover
        ]
        
        # Goalkeepers (Goal line, six yard box, penalty box)
        layouts["GK"] = [
            (28, 160, 1.2), # Centered on goal line
            (38, 160, 0.9), # Six yard box center
            (48, 150, 0.7), # Penalty spot area
            (55, 170, 0.6), # Penalty box boundaries
            (75, 160, 0.4), # Sweeper clearance zone
        ]
        
        # Map player positions to layout configurations
        pos_key = "CM"
        if pos in ["ST", "LST", "RST"]:
            pos_key = "ST"
        elif pos in ["LW", "LAM", "LM"]:
            pos_key = "LW"
        elif pos in ["RW", "RAM", "RM"]:
            pos_key = "RW"
        elif pos in ["CAM", "AM"]:
            pos_key = "CAM"
        elif pos in ["CM", "LCM", "RCM"]:
            pos_key = "CM"
        elif pos in ["LDM", "RDM"]:
            pos_key = "DM"
        elif pos in ["LB"]:
            pos_key = "LB"
        elif pos in ["RB"]:
            pos_key = "RB"
        elif pos in ["LCB", "RCB", "CB"]:
            pos_key = "CB"
        elif pos in ["GK"]:
            pos_key = "GK"
            
        base_points = layouts.get(pos_key, layouts["CM"])
        
        # Generate customized points with small organic variations (hotspots)
        custom_points = []
        for x, y, weight in base_points:
            dx = rng.randint(-15, 15)
            dy = rng.randint(-12, 12)
            dw = rng.uniform(-0.15, 0.15)
            
            # Clamp coordinates to stay within the bounds of the pitch
            new_x = max(25, min(475, x + dx))
            new_y = max(25, min(295, y + dy))
            new_weight = max(0.4, weight + dw)
            
            custom_points.append((new_x, new_y, new_weight))
            
        # Build the SVG elements
        svg_elements = []
        
        # Layer 1: Blue (Base coverage, wide)
        for cx, cy, w in custom_points:
            r = int(55 * w)
            svg_elements.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#2563eb" opacity="0.18"/>')
            
        # Layer 2: Green (Active presence, medium)
        for cx, cy, w in custom_points:
            r = int(40 * w)
            svg_elements.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#10b981" opacity="0.32"/>')
            
        # Layer 3: Yellow (High activity, medium-small)
        for cx, cy, w in custom_points:
            r = int(28 * w)
            svg_elements.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#eab308" opacity="0.45"/>')
            
        # Layer 4: Orange (Intense zones, small)
        for cx, cy, w in custom_points:
            r = int(18 * w)
            svg_elements.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#f97316" opacity="0.55"/>')
            
        # Layer 5: Red (Core peak touchzones, very small)
        for cx, cy, w in custom_points[:3]:
            r = int(10 * w)
            svg_elements.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#ef4444" opacity="0.75"/>')
            
        return "\n    ".join(svg_elements)

    def draw_graphical_heatmap_pitch(pos: str, player_name: str, sofa_id: str) -> str:
        heat_blobs = generate_graphical_heatmap(pos, player_name, sofa_id)
        
        svg_code = f"""
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 320" width="100%" height="auto" style="width: 100%; height: auto; aspect-ratio: 500 / 320; display: block; border-radius: 0.75rem; background-color: #0c1c12; border: 2px solid #1a3c25; box-shadow: inset 0 0 50px rgba(0,0,0,0.8); margin-bottom: 1rem;">
          <defs>
            <filter id="heat-blur" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="15"/>
            </filter>
            <pattern id="stripes" width="100" height="320" patternUnits="userSpaceOnUse">
              <rect x="0" y="0" width="50" height="320" fill="#0c1c12"/>
              <rect x="50" y="0" width="50" height="320" fill="#08150d"/>
            </pattern>
          </defs>
          
          <!-- Grass stripes -->
          <rect width="500" height="320" fill="url(#stripes)"/>
          
          <!-- Outer boundary lines -->
          <rect x="15" y="15" width="470" height="290" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="2"/>
          
          <!-- Center line -->
          <line x1="250" y1="15" x2="250" y2="305" stroke="rgba(255,255,255,0.18)" stroke-width="2"/>
          
          <!-- Center circle -->
          <circle cx="250" cy="160" r="45" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="2"/>
          <circle cx="250" cy="160" r="3" fill="rgba(255,255,255,0.3)"/>
          
          <!-- Left penalty box -->
          <rect x="15" y="65" width="75" height="190" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="2"/>
          <rect x="15" y="115" width="25" height="90" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="2"/>
          <circle cx="65" cy="160" r="2.5" fill="rgba(255,255,255,0.3)"/>
          <path d="M 90 130 A 45 45 0 0 1 90 190" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="2"/>
          
          <!-- Right penalty box -->
          <rect x="410" y="65" width="75" height="190" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="2"/>
          <rect x="460" y="115" width="25" height="90" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="2"/>
          <circle cx="435" cy="160" r="2.5" fill="rgba(255,255,255,0.3)"/>
          <path d="M 410 130 A 45 45 0 0 0 410 190" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="2"/>
          
          <!-- Corner arcs -->
          <path d="M 15 25 A 10 10 0 0 0 25 15" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="1.5"/>
          <path d="M 15 295 A 10 10 0 0 1 25 305" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="1.5"/>
          <path d="M 485 25 A 10 10 0 0 1 475 15" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="1.5"/>
          <path d="M 485 295 A 10 10 0 0 0 475 305" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="1.5"/>
          
          <!-- Goals -->
          <rect x="5" y="140" width="10" height="40" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="1.5"/>
          <rect x="485" y="140" width="10" height="40" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="1.5"/>
          
          <!-- HEATMAP OVERLAY LAYER -->
          <g filter="url(#heat-blur)">
            {heat_blobs}
          </g>
        </svg>
        """
        return svg_code

    with col_pheat:
        st.markdown("#### 🗺️ SofaScore Positional Intensity Heatmap")
        
        # Check if the player has a valid SofaScore ID to show the widget
        sofa_id = selected_p_obj.get("sofa_id", "") if selected_p_obj else ""
        
        # Setup display mode selector
        options_list = ["🔥 Graphical Heatmap", "🗺️ Live SofaScore Widget", "📊 Classic ASCII Map"] if sofa_id else ["🔥 Graphical Heatmap", "📊 Classic ASCII Map"]
        widget_mode = st.segmented_control(
            "Heatmap Display Mode:",
            options=options_list,
            default="🔥 Graphical Heatmap",
            key=f"widget_mode_{sofa_id}" if sofa_id else "widget_mode_no_sofa"
        )
            
        if widget_mode == "🔥 Graphical Heatmap":
            heatmap_svg = draw_graphical_heatmap_pitch(pos, p_name, sofa_id)
            st.markdown(clean_html(heatmap_svg), unsafe_allow_html=True)
            st.caption("Intensity scale: Red (Peak Touch Zone) ➔ Orange ➔ Yellow ➔ Green ➔ Blue (Coverage Boundary)")
        elif widget_mode == "🗺️ Live SofaScore Widget":
            st.html(f"""
            <iframe 
                src="https://widgets.sofascore.com/embed/player/{sofa_id}?widgetTheme=dark" 
                style="height:730px!important;width:100%!important;max-width:480px!important;border:none;border-radius:0.75rem;" 
                frameborder="0" 
                scrolling="no"
                referrerpolicy="no-referrer">
            </iframe>
            """)
        else:
            # Custom Heatmap layouts based on player position
            if pos in ["ST", "LST", "RST"]:
                heatmap_grid = (
                    " ┌────────────────────────────────────────┐ \n"
                    " │        ░  ░  ▒  ▓  ▓  ▒  ░  ░          │ [OPP BOX]\n"
                    " │        ░  ░  ▒  █  █  ▒  ░  ░          │ \n"
                    " │        ░  ░  ░  ▓  ▓  ░  ░  ░          │ \n"
                    " │        ░  ░  ░  ▒  ▒  ░  ░  ░          │ [MIDFIELD]\n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ [OWN HALF]\n"
                    " └────────────────────────────────────────┘ "
                )
            elif pos in ["LW", "LAM", "LM"]:
                heatmap_grid = (
                    " ┌────────────────────────────────────────┐ \n"
                    " │        █  █  ▓  ▒  ░  ░  ░  ░          │ [OPP BOX]\n"
                    " │        █  █  ▓  ░  ░  ░  ░  ░          │ \n"
                    " │        ▓  ▓  ▒  ░  ░  ░  ░  ░          │ \n"
                    " │        ▒  ▒  ░  ░  ░  ░  ░  ░          │ [MIDFIELD]\n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ [OWN HALF]\n"
                    " └────────────────────────────────────────┘ "
                )
            elif pos in ["RW", "RAM", "RM"]:
                heatmap_grid = (
                    " ┌────────────────────────────────────────┐ \n"
                    " │        ░  ░  ░  ░  ▒  ▓  █  █          │ [OPP BOX]\n"
                    " │        ░  ░  ░  ░  ░  ▓  █  █          │ \n"
                    " │        ░  ░  ░  ░  ░  ▒  ▓  ▓          │ \n"
                    " │        ░  ░  ░  ░  ░  ░  ▒  ▒          │ [MIDFIELD]\n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ [OWN HALF]\n"
                    " └────────────────────────────────────────┘ "
                )
            elif pos in ["CAM", "CM", "LCM", "RCM", "AM"]:
                heatmap_grid = (
                    " ┌────────────────────────────────────────┐ \n"
                    " │        ░  ░  ▒  ▓  ▓  ▒  ░  ░          │ [OPP BOX]\n"
                    " │        ░  ▒  ▓  █  █  ▓  ▒  ░          │ \n"
                    " │        ░  ▒  ▓  █  █  ▓  ▒  ░          │ \n"
                    " │        ░  ░  ▒  ▓  ▓  ▒  ░  ░          │ [MIDFIELD]\n"
                    " │        ░  ░  ░  ▒  ▒  ░  ░  ░          │ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ [OWN HALF]\n"
                    " └────────────────────────────────────────┘ "
                )
            elif pos in ["LDM", "RDM"]:
                heatmap_grid = (
                    " ┌────────────────────────────────────────┐ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ [OPP BOX]\n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ \n"
                    " │        ░  ░  ▒  ▒  ▒  ▒  ░  ░          │ \n"
                    " │        ░  ▒  ▓  █  █  ▓  ▒  ░          │ [MIDFIELD]\n"
                    " │        ░  ▒  ▓  █  █  ▓  ▒  ░          │ \n"
                    " │        ░  ░  ▒  ▓  ▓  ▒  ░  ░          │ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ [OWN HALF]\n"
                    " └────────────────────────────────────────┘ "
                )
            elif pos in ["LB", "LCB", "RCB", "RB"]:
                heatmap_grid = (
                    " ┌────────────────────────────────────────┐ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ [OPP BOX]\n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ [MIDFIELD]\n"
                    " │        ░  ░  ▒  ▒  ▒  ▒  ░  ░          │ \n"
                    " │        ░  ▒  ▓  █  █  ▓  ▒  ░          │ \n"
                    " │        ░  ▒  ▓  █  █  ▓  ▒  ░          │ [OWN HALF]\n"
                    " └────────────────────────────────────────┘ "
                )
            else: # Goalkeeper
                heatmap_grid = (
                    " ┌────────────────────────────────────────┐ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ [OPP BOX]\n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ [MIDFIELD]\n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ \n"
                    " │        ░  ░  ░  ░  ░  ░  ░  ░          │ \n"
                    " │        ░  ░  ▒  █  █  ▒  ░  ░          │ [GOAL BOX]\n"
                    " └────────────────────────────────────────┘ "
                )
                
            st.code(heatmap_grid, language="text")
            st.caption("Intensity scale: █ (High Touch Zone) ➔ ▓ ➔ ▒ ➔ ░ (Low Touch Zone)")
        
    st.markdown("---")
    
    # 5. Submit to RAG scout assessment
    st.markdown("#### 🧠 Ask FootBot to Analyze this SofaScore Data")
    st.markdown("Automatically submit these SofaScore momentum timelines, box stats, and player heatmap rating to our elite RAG tactical engine for a professional scout assessment.")
    
    if st.button("📊 Generate AI Scouting Analysis", use_container_width=True):
        custom_query = (
            f"Analyze the tactical metrics and player rating statistics from the match: {clean_match_name}. "
            f"Home stats: Possession {possession_home}%, Shots {shots_home}. Away stats: Possession {possession_away}%, Shots {shots_away}. "
            f"Include tactical evaluations of the selected player ({selected_player}) who finished with an elite SofaScore rating of {rating}."
        )
        st.session_state.clicked_preset = custom_query
        st.success("SofaScore analytics captured! Switching to AI Chat to generate assessment report...")
        st.rerun()
