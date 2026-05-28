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
    """Queries backend live matches feed."""
    try:
        response = requests.get(f"{BACKEND_URL}/live-matches", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return {"status": "error", "count": 0, "feed": []}

def get_historical_matches_feed() -> List[Dict[str, Any]]:
    """Queries backend historical matches database."""
    try:
        response = requests.get(f"{BACKEND_URL}/historical-matches", timeout=10)
        if response.status_code == 200:
            return response.json()
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
    
    # 1. Match Selector
    historical_matches = get_historical_matches_feed()
    match_options = []
    if historical_matches:
        for m in historical_matches:
            hs = m["home_score"] if m["home_score"] is not None else 0
            as_ = m["away_score"] if m["away_score"] is not None else 0
            match_options.append(f"🏆 {m['home_team']} {hs} - {as_} {m['away_team']} ({m['match_date']})")
    
    # Defaults
    match_options.extend([
        "🏆 Manchester City 3 - 3 Real Madrid (Champions League)",
        "🏆 Arsenal 2 - 2 Bayern Munich (Champions League)",
        "🏆 Liverpool 1 - 1 Manchester City (Premier League)"
    ])
    
    selected_match = st.selectbox("Select Match to Analyze:", options=match_options)
    
    # Clean selected match name
    clean_match_name = selected_match.replace("🏆 ", "").split(" (")[0]
    
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
        
        # Plot styled Streamlit Area Chart
        st.area_chart(mom_df, use_container_width=True)
        
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
        
    st.markdown("---")
    
    st.markdown("### 👤 SofaScore Positional Rating & Heatmap Index")
    st.markdown("Select any active player from your customized formation to view their performance ratings and intensity zones.")
    
    col_pctrl, col_pheat = st.columns([1, 1])
    
    # Retrieve customized player names
    lw_lbl = locals().get("custom_lw", "LW")
    rw_lbl = locals().get("custom_rw", "RW")
    cf_lbl = locals().get("custom_cf", "CF")
    am_lbl = locals().get("custom_am", "AM")
    cm_lbl = locals().get("custom_cm", "CM")
    dm_lbl = locals().get("custom_dm", "DM")
    cb_lbl = locals().get("custom_cb", "CB")
    gk_lbl = locals().get("custom_gk", "GK")
    
    player_options = [
        f"🎯 Striker ({cf_lbl})",
        f"⚡ Left Winger ({lw_lbl})",
        f"⚡ Right Winger ({rw_lbl})",
        f"🪄 Attacking Midfielder ({am_lbl})",
        f"🧠 Central Midfielder ({cm_lbl})",
        f"🛡️ Holding Anchor ({dm_lbl})",
        f"🧱 Center Back ({cb_lbl})",
        f"🧤 Goalkeeper ({gk_lbl})"
    ]
    
    with col_pctrl:
        selected_player = st.selectbox("Select Player Slot:", options=player_options)
        
        # SofaScore ratings and accurate bio details based on selection
        if "Striker" in selected_player:
            rating, rating_color = 8.4, "#10b981" # Green
            phy, cre, dfn, tec, tac, att = 75, 70, 30, 85, 80, 92
            p_name = "Erling Haaland"
            p_team = "Manchester City"
            p_nat = "🇳🇴 Norway"
            p_age = "25"
            p_foot = "Left"
            p_height = "194 cm"
            p_weight = "88 kg"
            p_jersey = "#9"
            p_val = "€180M"
            p_trait = "Acrobatic target man & supreme finisher"
        elif "Left Winger" in selected_player:
            rating, rating_color = 7.8, "#10b981"
            phy, cre, dfn, tec, tac, att = 88, 82, 35, 84, 75, 80
            p_name = "Phil Foden"
            p_team = "Manchester City"
            p_nat = "🏴󠁧󠁢󠁥󠁮󠁧󠁿 England"
            p_age = "25"
            p_foot = "Left"
            p_height = "179 cm"
            p_weight = "70 kg"
            p_jersey = "#47"
            p_val = "€150M"
            p_trait = "Highly creative interior ball-carrier"
        elif "Right Winger" in selected_player:
            rating, rating_color = 7.9, "#10b981"
            phy, cre, dfn, tec, tac, att = 82, 85, 38, 88, 79, 78
            p_name = "Bernardo Silva"
            p_team = "Manchester City"
            p_nat = "🇵🇹 Portugal"
            p_age = "31"
            p_foot = "Left"
            p_height = "173 cm"
            p_weight = "64 kg"
            p_jersey = "#20"
            p_val = "€70M"
            p_trait = "Relentless presser & half-space facilitator"
        elif "Attacking" in selected_player:
            rating, rating_color = 8.1, "#10b981"
            phy, cre, dfn, tec, tac, att = 70, 90, 48, 92, 88, 75
            p_name = "Kevin De Bruyne"
            p_team = "Manchester City"
            p_nat = "🇧🇪 Belgium"
            p_age = "34"
            p_foot = "Right"
            p_height = "181 cm"
            p_weight = "75 kg"
            p_jersey = "#17"
            p_val = "€60M"
            p_trait = "Master crosser & elite play creator"
        elif "Central Midfielder" in selected_player:
            rating, rating_color = 8.2, "#10b981"
            phy, cre, dfn, tec, tac, att = 75, 82, 60, 88, 85, 78
            p_name = "Jude Bellingham"
            p_team = "Real Madrid"
            p_nat = "🏴󠁧󠁢󠁥󠁮󠁧󠁿 England"
            p_age = "22"
            p_foot = "Right"
            p_height = "186 cm"
            p_weight = "75 kg"
            p_jersey = "#5"
            p_val = "€180M"
            p_trait = "Powerful box-to-box engine"
        elif "Holding Anchor" in selected_player:
            rating, rating_color = 7.5, "#10b981"
            phy, cre, dfn, tec, tac, att = 80, 68, 85, 80, 90, 50
            p_name = "Rodri (Rodrigo Hernández)"
            p_team = "Manchester City"
            p_nat = "🇪🇸 Spain"
            p_age = "29"
            p_foot = "Right"
            p_height = "190 cm"
            p_weight = "82 kg"
            p_jersey = "#16"
            p_val = "€120M"
            p_trait = "Tactical pivot & rest-defense sweeper"
        elif "Center Back" in selected_player:
            rating, rating_color = 7.2, "#34d399" # Teal
            phy, cre, dfn, tec, tac, att = 85, 50, 88, 65, 84, 40
            p_name = "Rúben Dias"
            p_team = "Manchester City"
            p_nat = "🇵🇹 Portugal"
            p_age = "28"
            p_foot = "Right"
            p_height = "187 cm"
            p_weight = "83 kg"
            p_jersey = "#3"
            p_val = "€80M"
            p_trait = "Commanding stopper & backline leader"
        else: # Goalkeeper
            rating, rating_color = 6.9, "#f59e0b" # Orange
            phy, cre, dfn, tec, tac, att = 75, 40, 90, 60, 85, 10
            p_name = "Ederson Moraes"
            p_team = "Manchester City"
            p_nat = "🇧🇷 Brazil"
            p_age = "32"
            p_foot = "Left"
            p_height = "188 cm"
            p_weight = "86 kg"
            p_jersey = "#31"
            p_val = "€35M"
            p_trait = "Sweeper-keeper & pin-point distributor"
            
        # 1. Performance rating card
        st.markdown(f"""
        <div style="background-color: #0c1210; border: 1px solid #142820; border-radius: 0.75rem; padding: 1.2rem; display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.2rem;">
            <div>
                <h4 style="margin: 0; color: #f3f4f6;">SofaScore Performance Rating</h4>
                <p style="margin: 0.2rem 0 0 0; color: #6b7280; font-size: 0.85rem;">Scouting telemetry index based on active matchday</p>
            </div>
            <div style="background-color: {rating_color}; color: #000; font-size: 1.8rem; font-weight: 800; padding: 0.5rem 1rem; border-radius: 0.5rem; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.3);">
                {rating}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # 2. Detailed Player Bio Profile Card
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
        
        st.markdown("##### 🎭 Playstyle Attribute Hexagon Profile")
        
        def render_attribute(label: str, pct: int):
            filled = "█" * (pct // 10)
            empty = "░" * (10 - len(filled))
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.4rem; font-size: 0.85rem;">
                <span style="color: #9ca3af;">{label}</span>
                <span style="font-family: monospace; color: #34d399;">{filled}{empty} {pct}%</span>
            </div>
            """, unsafe_allow_html=True)
            
        render_attribute("🚀 Attacking & Finishing", att)
        render_attribute("🪄 Creativity & Key Passes", cre)
        render_attribute("🏃‍♂️ Physicality & Workrate", phy)
        render_attribute("🧠 Tactical Scanning & Rest-Defense", tac)
        render_attribute("🛡️ Defending & Swarming Interceptions", dfn)
        
    with col_pheat:
        st.markdown("#### 🗺️ SofaScore Positional Intensity Heatmap")
        
        # Custom Heatmap layouts based on player slot selected
        if "Striker" in selected_player:
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
        elif "Left Winger" in selected_player:
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
        elif "Right Winger" in selected_player:
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
        elif "Attacking" in selected_player or "Central Midfielder" in selected_player:
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
        elif "Holding Anchor" in selected_player:
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
        elif "Center Back" in selected_player:
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
