import pytest
from fastapi.testclient import TestClient
from main import app, DB_PATH
import os

client = TestClient(app)

# Optional: Clean up the test database before/after tests if desired, 
# or let it run against users.db. For clean tests, you can use a separate test db.

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_register_user():
    # Register a brand new unique user
    response = client.post(
        "/register",
        json={"username": "testuser_pytest", "password": "securepassword123"}
    )
    # 201 Created or 409 Conflict (if ran multiple times)
    assert response.status_code in [201, 409]

def test_register_duplicate_user():
    # Register once
    client.post(
        "/register",
        json={"username": "duplicate_guy", "password": "securepassword123"}
    )
    # Try registering again with the exact same username
    response = client.post(
        "/register",
        json={"username": "duplicate_guy", "password": "securepassword123"}
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Username already taken"

def test_login_and_protected_route():
    # 1. Ensure user exists
    client.post(
        "/register",
        json={"username": "loginguy", "password": "correctpassword1"}
    )
    
    # 2. Login to get token
    login_response = client.post(
        "/login",
        json={"username": "loginguy", "password": "correctpassword1"}
    )
    assert login_response.status_code == 200
    data = login_response.json()
    assert "access_token" in data
    token = data["access_token"]
    
    # 3. Access protected route /me with the token
    me_response = client.get(
        "/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_response.status_code == 200
    assert me_response.json() == {"username": "loginguy"}

def test_rate_limiter():
    # Hit the login route 6 times with a wrong password to trigger 429
    bad_payload = {"username": "nonexistent", "password": "wrongpassword"}
    
    status_codes = []
    for _ in range(6):
        res = client.post("/login", json=bad_payload)
        status_codes.append(res.status_code)
        
    # First 5 attempts should fail with 401 (Invalid username or password)
    assert status_codes[:5] == [401, 401, 401, 401, 401]
    # The 6th attempt should be blocked with 429 (Too Many Requests)
    assert status_codes[5] == 429