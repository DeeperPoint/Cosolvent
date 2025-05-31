import pytest
from fastapi.testclient import TestClient
from services.llm_orchestration_service.src.main import app

@pytest.fixture
def client():
    return TestClient(app)
