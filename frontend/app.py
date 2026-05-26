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
    st.session_state.authenticated = False
if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = None
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

# --- Authentication Gateway Lock Panel ---
if not st.session_state.authenticated:
    st.markdown("""
    <div style='text-align: center; padding: 2.5rem; background: rgba(12, 18, 16, 0.85); border: 2px solid #0d9488; border-radius: 1rem; max-width: 650px; margin: 2rem auto; box-shadow: 0 10px 30px -5px rgba(0,0,0,0.6);'>
        <h1 style='font-size: 3.5rem; margin-bottom: 0.8rem;'>🔒</h1>
        <h2 style='color: #10b981; font-family: "Space Grotesk"; margin-bottom: 0.5rem;'>FOOTBOT COACHING PORTAL LOCK</h2>
        <p style='color: #9ca3af; font-size: 1rem; margin-bottom: 1.5rem;'>Certified coaches must authenticate or register to access dynamic tactics analysis databases, live score telemetries, and 2D formation modules.</p>
    </div>
    """, unsafe_allow_html=True)
    
    auth_tab1, auth_tab2 = st.tabs(["🔑 Coach Sign In", "📝 Register New Profile"])
    
    with auth_tab1:
        with st.form("login_form"):
            st.markdown("### Sign In to FootBot")
            username = st.text_input("Username:", placeholder="Enter coach username")
            password = st.text_input("Password:", type="password", placeholder="Enter secure password")
            submitted = st.form_submit_button("🔑 Unlock Console", use_container_width=True)
            
            if submitted:
                if username.strip() and password.strip():
                    try:
                        res = requests.post(f"{BACKEND_URL}/login", json={
                            "username": username.strip(),
                            "password": password.strip()
                        }, timeout=10)
                        if res.status_code == 200:
                            data = res.json()
                            st.session_state.authenticated = True
                            st.session_state.token = data["token"]
                            st.session_state.username = data["username"]
                            st.success(f"Welcome back, Coach {data['username']}! Unlocking platform...")
                            st.rerun()
                        else:
                            st.error(f"Authentication Failed: {res.json().get('detail', 'Invalid credentials')}")
                    except Exception as e:
                        st.error(f"FastAPI connection offline: {str(e)}")
                else:
                    st.warning("Please fill out both username and password.")
                    
    with auth_tab2:
        with st.form("register_form"):
            st.markdown("### Coach Registration Form")
            new_user = st.text_input("Choose Coach Username:", placeholder="e.g. Coach Guardiola")
            new_pass = st.text_input("Choose Password:", type="password", placeholder="Minimum 4 characters")
            submitted_reg = st.form_submit_button("📝 Register Coach Profile", use_container_width=True)
            
            if submitted_reg:
                if len(new_user.strip()) >= 3 and len(new_pass.strip()) >= 4:
                    try:
                        res = requests.post(f"{BACKEND_URL}/register", json={
                            "username": new_user.strip(),
                            "password": new_pass.strip()
                        }, timeout=10)
                        if res.status_code == 201:
                            data = res.json()
                            st.session_state.authenticated = True
                            st.session_state.token = data["token"]
                            st.session_state.username = data["username"]
                            st.success(f"Coach Profile '{data['username']}' registered successfully! Redirecting...")
                            st.rerun()
                        else:
                            st.error(f"Registration Failed: {res.json().get('detail', 'Username already exists')}")
                    except Exception as e:
                        st.error(f"FastAPI connection offline: {str(e)}")
                else:
                    st.warning("Username must be at least 3 chars; password at least 4 chars.")
                    
    st.stop()  # Lock UI execution until signed in

# --- Authenticated Sidebar Control Panel ---
st.sidebar.markdown(f"<h3 style='color:#10b981; font-family:\"Space Grotesk\"; margin-bottom:0;'>👤 COACH: {st.session_state.username.upper()}</h3>", unsafe_allow_html=True)
if st.sidebar.button("🔓 Sign Out", use_container_width=True):
    st.session_state.authenticated = False
    st.session_state.token = None
    st.session_state.username = None
    st.session_state.messages = []
    st.session_state.active_session_id = None
    st.rerun()

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
tab_chat, tab_pitch, tab_live = st.tabs(["💬 Tactical AI Chat", "📋 2D Formation Board", "⚽ Live & Historical Scorelines"])

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
        
        assess_button = st.button("🧠 Submit Formation for RAG Assessment", use_container_width=True)
        
    with col_map:
        st.markdown("#### Live 2D Tactical Pitch Preview")
        
        # Build ASCII mapping representation
        lines = [
            " ┌──────────────────────────────────────────┐ ",
            " │             [ OPPONENT GOAL ]            │ ",
            " ├───────────────────┬──────────────────────┤ "
        ]
        
        w_l = "LW " if "wide" in opt_wingers.lower() else "  LW"
        w_r = "RW " if "wide" in opt_wingers.lower() else "  RW"
        
        if "3-2-4-1" in sel_formation:
            lines.append(f" │    {w_l}         AM      AM         {w_r}   │")
            lines.append(f" │                                          │")
            lines.append(" │               DM      DM                 │")
            lines.append(f" │                                          │")
            lines.append(" │            CB     CB     CB              │")
        elif "4-3-3" in sel_formation:
            lines.append(f" │    {w_l}            CF            {w_r}   │")
            lines.append(f" │                                          │")
            if "Box" in opt_midfield:
                lines.append(" │            AM            AM              │")
                lines.append(" │                 DM                       │")
            else:
                lines.append(" │            CM            CM              │")
                lines.append(" │                 DM                       │")
            lines.append(f" │                                          │")
            if opt_inverted:
                lines.append(" │        LB       CB    CB       RB (Inv)  │")
            else:
                lines.append(" │        LB       CB    CB       RB        │")
        elif "5-4-1" in sel_formation:
            lines.append(f" │                  CF                      │")
            lines.append(f" │    {w_l}                              {w_r}   │")
            lines.append(" │               CM      CM                 │")
            lines.append(f" │                                          │")
            lines.append(" │     LWB    CB    CB    CB    RWB         │")
        else: # 4-4-2 Diamond
            lines.append(f" │            CF            CF              │")
            lines.append(f" │                                          │")
            lines.append(" │                  AM                      │")
            lines.append(" │            LM            RM              │")
            lines.append(" │                  DM                      │")
            lines.append(" │        LB       CB    CB       RB        │")
            
        lines.extend([
            " │                                          │",
            " ├───────────────────┴──────────────────────┤ ",
            " │                 [ GK ]                   │ ",
            " └──────────────────────────────────────────┘ "
        ])
        
        pitch_ascii = "\n".join(lines)
        
        st.markdown(f"""
        <div class='pitch-container'>
            <pre class='pitch-ascii'>{pitch_ascii}</pre>
            <p style='color:#9ca3af; font-size:0.85rem; margin-top:0.4rem;'>Pressing Height: <b>{sel_pressing.upper()}</b></p>
        </div>
        """, unsafe_allow_html=True)
        
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
