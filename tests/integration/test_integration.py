"""Integration tests for OasisAI MVP."""

from __future__ import annotations

import time

import httpx
import pytest

BASE_URL = "http://localhost:8080"
TIMEOUT = 60.0


@pytest.fixture
def client() -> httpx.Client:
    """Create an HTTP client for testing."""
    return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)


@pytest.fixture(autouse=True)
def wait_for_services() -> None:
    """Wait for services to be healthy before running tests."""
    client = httpx.Client(timeout=10.0)
    for attempt in range(30):
        try:
            resp = client.get(f"{BASE_URL}/health")
            if resp.status_code == 200:
                break
        except Exception:
            if attempt < 29:
                time.sleep(1)
            else:
                raise RuntimeError("Services not responding after 30 seconds")


class TestGatewayHealth:
    """Test gateway health endpoints."""

    def test_health_check(self, client: httpx.Client) -> None:
        """Test gateway health endpoint."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "oasis-gateway"


class TestIndexing:
    """Test repository indexing."""

    def test_index_sample_app(self, client: httpx.Client) -> None:
        """Test indexing a sample repository."""
        payload = {"repo_path": "/repos/sample-app", "repo_name": "sample-app"}
        resp = client.post("/index", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["repo_name"] == "sample-app"
        assert data["chunks_indexed"] > 0
        assert data["status"] == "ok"


class TestSearch:
    """Test semantic search functionality."""

    def test_search_query(self, client: httpx.Client) -> None:
        """Test semantic search."""
        # Index first
        client.post(
            "/index",
            json={"repo_path": "/repos/sample-app", "repo_name": "sample-app"},
        )
        time.sleep(2)

        # Search
        payload = {"query": "user validation", "top_k": 3}
        resp = client.post("/search", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        # Results may be empty if indexing not completed

    def test_search_with_repo_filter(self, client: httpx.Client) -> None:
        """Test search with repository filter."""
        payload = {
            "query": "database operations",
            "repo": "sample-app",
            "top_k": 5,
        }
        resp = client.post("/search", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data


class TestAskEndpoint:
    """Test ask (question answering) endpoint."""

    def test_ask_question(self, client: httpx.Client) -> None:
        """Test asking a question about the codebase."""
        # Index first
        client.post(
            "/index",
            json={"repo_path": "/repos/sample-app", "repo_name": "sample-app"},
        )
        time.sleep(2)

        payload = {
            "question": "What classes are defined in the models module?",
            "repo": "sample-app",
            "top_k": 5,
        }
        resp = client.post("/ask", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "sources" in data


class TestRefactorEndpoint:
    """Test refactor endpoint."""

    def test_refactor_request(self, client: httpx.Client) -> None:
        """Test generating a refactor plan."""
        # Index first
        client.post(
            "/index",
            json={"repo_path": "/repos/sample-app", "repo_name": "sample-app"},
        )
        time.sleep(2)

        payload = {
            "instruction": "Add proper error handling to all functions",
            "repo": "sample-app",
            "top_k": 5,
        }
        resp = client.post("/refactor", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "plan" in data
        assert "patches" in data
        assert "sources" in data


class TestRequestValidation:
    """Test request validation."""

    def test_search_empty_query(self, client: httpx.Client) -> None:
        """Test search with empty query."""
        payload = {"query": ""}
        resp = client.post("/search", json=payload)
        assert resp.status_code == 422  # Validation error

    def test_ask_empty_question(self, client: httpx.Client) -> None:
        """Test ask with empty question."""
        payload = {"question": ""}
        resp = client.post("/ask", json=payload)
        assert resp.status_code == 422  # Validation error

    def test_refactor_empty_instruction(self, client: httpx.Client) -> None:
        """Test refactor with empty instruction."""
        payload = {"instruction": ""}
        resp = client.post("/refactor", json=payload)
        assert resp.status_code == 422  # Validation error

    def test_index_missing_fields(self, client: httpx.Client) -> None:
        """Test index with missing fields."""
        payload = {"repo_path": "/repos/sample"}
        resp = client.post("/index", json=payload)
        assert resp.status_code == 422  # Validation error


class TestResponseFormat:
    """Test response formats."""

    def test_search_response_format(self, client: httpx.Client) -> None:
        """Test that search returns proper format."""
        payload = {"query": "test", "top_k": 3}
        resp = client.post("/search", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_index_response_format(self, client: httpx.Client) -> None:
        """Test that index returns proper format."""
        payload = {"repo_path": "/repos/sample-app", "repo_name": "sample-app"}
        resp = client.post("/index", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "repo_name" in data
        assert "chunks_indexed" in data
        assert "status" in data
