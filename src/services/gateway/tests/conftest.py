import pytest
from fastapi.testclient import TestClient
from services.gateway.src.main import app

@pytest.fixture
def client():
    return TestClient(app)