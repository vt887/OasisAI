"""Tests for the FastAPI gateway endpoints using TestClient."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Mock chromadb and httpx before importing gateway
with patch("chromadb.HttpClient"), patch("httpx.Client"):
    # Add gateway to path
    sys.path.insert(
        0, str(Path(__file__).parent.parent.parent / "services" / "gateway")
    )
    import main as gateway_main


@pytest.fixture
def client() -> TestClient:
    return TestClient(gateway_main.app)


class TestGatewayHealth:
    def test_health(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "oasis-gateway"


class TestGatewayAsk:
    def test_ask_forwards_to_agent(self, client: TestClient) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Authentication uses JWT tokens.",
            "sources": [],
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            gateway_main._http, "post", return_value=mock_response
        ):
            resp = client.post(
                "/ask",
                json={
                    "question": "How does authentication work?",
                    "repo": "myrepo",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert data["answer"] == "Authentication uses JWT tokens."

    def test_ask_empty_question_rejected(self, client: TestClient) -> None:
        resp = client.post("/ask", json={"question": ""})
        assert resp.status_code == 422

    def test_ask_upstream_error_returns_503(self, client: TestClient) -> None:
        import httpx

        with patch.object(
            gateway_main._http,
            "post",
            side_effect=httpx.ConnectError("refused"),
        ):
            resp = client.post("/ask", json={"question": "test"})
        assert resp.status_code == 503


class TestGatewayRefactor:
    def test_refactor_forwards_to_agent(self, client: TestClient) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "plan": "1. Extract DB logic\n2. Create repository.py",
            "patches": ["--- a/db.py\n+++ b/db.py\n@@..."],
            "sources": [],
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            gateway_main._http, "post", return_value=mock_response
        ):
            resp = client.post(
                "/refactor",
                json={"instruction": "Extract DB logic", "repo": "myrepo"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "plan" in data
        assert "patches" in data

    def test_refactor_empty_instruction_rejected(
        self, client: TestClient
    ) -> None:
        resp = client.post("/refactor", json={"instruction": ""})
        assert resp.status_code == 422


class TestGatewayIndex:
    def test_index_forwards_to_indexer(self, client: TestClient) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "repo_name": "myrepo",
            "chunks_indexed": 42,
            "status": "ok",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            gateway_main._http, "post", return_value=mock_response
        ):
            resp = client.post(
                "/index",
                json={"repo_path": "/repos/myrepo", "repo_name": "myrepo"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["chunks_indexed"] == 42
        assert data["repo_name"] == "myrepo"
