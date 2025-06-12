import sys
import os

# Ensure metadata_service/src is on sys.path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import pytest
from fastapi.testclient import TestClient

# Import app from main module
from main import app

@pytest.fixture
def client():
    return TestClient(app)