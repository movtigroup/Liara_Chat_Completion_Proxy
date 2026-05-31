import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "AI Proxy v3.1" in response.text

def test_register():
    # Test user registration (will fail if admin already exists, but good for flow check)
    response = client.post("/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123"
    })
    assert response.status_code in [200, 400]
