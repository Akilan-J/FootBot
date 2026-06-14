import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    print("--- 1. Testing GET /health ---")
    res = requests.get(f"{BASE_URL}/health")
    print("Status:", res.status_code)
    print("Body:", res.json())
    assert res.status_code == 200, "Health check failed"

def test_auth():
    print("\n--- 2. Testing POST /register and POST /login ---")
    username = "test_user_api_new"
    password = "password123"
    
    # Try register
    res = requests.post(f"{BASE_URL}/register", json={"username": username, "password": password})
    print("Register Status:", res.status_code)
    if res.status_code in [201, 200]:
        token = res.json()["token"]
        print("Register Success, Token:", token)
    else:
        print("Register detail:", res.json())
        # Try login instead
        res = requests.post(f"{BASE_URL}/login", json={"username": username, "password": password})
        print("Login Status:", res.status_code)
        assert res.status_code == 200, "Auth failed"
        token = res.json()["token"]
        print("Login Success, Token:", token)
    return token

def test_chat(token):
    print("\n--- 3. Testing POST /chat with tactical query ---")
    headers = {"X-User-Token": token}
    payload = {
        "query": "Analyse this tactical shape in detail: Formation: 4-3-3 Midfield Geometry: flat Defensive Line: Mid Block Inverted Fullbacks: Inactive",
        "temperature": 0.2,
        "top_k": 3
    }
    res = requests.post(f"{BASE_URL}/chat", json=payload, headers=headers)
    print("Chat Status:", res.status_code)
    assert res.status_code == 200, "Chat request failed"
    data = res.json()
    print("Chat Query:", data["query"])
    print("Response snippet:", data["response"][:150] + "...")
    print("Session ID:", data["session_id"])
    print("RAG Active:", data["is_rag_active"])
    print("Sources count:", len(data["sources"]))
    for src in data["sources"][:2]:
        print(f" - Source: {src['source']}, Type: {src['type']}, Score: {src['score']}")
    
    return data["session_id"]

def test_sessions(token, session_id):
    print("\n--- 4. Testing GET /sessions ---")
    headers = {"X-User-Token": token}
    res = requests.get(f"{BASE_URL}/sessions", headers=headers)
    print("Sessions Status:", res.status_code)
    assert res.status_code == 200
    sessions = res.json()
    print("Found sessions count:", len(sessions))
    has_our_session = any(s["id"] == session_id for s in sessions)
    print("Contains current session:", has_our_session)
    assert has_our_session, "Session list does not contain current session"

    print("\n--- 5. Testing GET /sessions/{session_id}/messages ---")
    res = requests.get(f"{BASE_URL}/sessions/{session_id}/messages", headers=headers)
    print("Messages Status:", res.status_code)
    assert res.status_code == 200
    messages = res.json()
    print("Messages count:", len(messages))
    assert len(messages) >= 2, "Should have user and assistant messages"

def test_pdf(token, session_id):
    print("\n--- 6. Testing GET /sessions/{session_id}/pdf ---")
    headers = {"X-User-Token": token}
    res = requests.get(f"{BASE_URL}/sessions/{session_id}/pdf", headers=headers)
    print("PDF Status:", res.status_code)
    assert res.status_code == 200
    content_type = res.headers.get("Content-Type")
    print("Content-Type:", content_type)
    assert "pdf" in content_type.lower()
    # Verify PDF signature (%PDF)
    signature = res.content[:4]
    print("PDF Signature:", signature)
    assert signature == b"%PDF", "Invalid PDF signature"

def test_roster():
    print("\n--- 7. Testing GET /roster ---")
    res = requests.get(f"{BASE_URL}/roster", params={"team_name": "Manchester City"})
    print("Roster Status:", res.status_code)
    assert res.status_code == 200
    data = res.json()
    print("Roster status field:", data["status"])
    print("Players count:", len(data["roster"]))
    if data["roster"]:
        p = data["roster"][0]
        print("Example player:", p)

def test_player_image():
    print("\n--- 8. Testing GET /player/image ---")
    res = requests.get(f"{BASE_URL}/player/image", params={"name": "Rodri", "pos": "DM"})
    print("Image Status:", res.status_code)
    assert res.status_code == 200
    print("Image Content-Type:", res.headers.get("Content-Type"))

if __name__ == "__main__":
    try:
        test_health()
        token = test_auth()
        session_id = test_chat(token)
        test_sessions(token, session_id)
        test_pdf(token, session_id)
        test_roster()
        test_player_image()
        print("\n🎉 ALL BACKEND ENDPOINT TESTS PASSED SUCCESSFULY!")
    except AssertionError as e:
        print("\n❌ TEST FAILED:", e)
        sys.exit(1)
    except Exception as e:
        print("\n🚨 ERROR RUNNING TESTS:", e)
        sys.exit(1)
