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

    def test_ask_get_returns_usage(self, client: TestClient) -> None:
        resp = client.get("/ask")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Use POST /ask with JSON body"

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


class TestGatewaySearch:
    def test_search_queries_chroma_via_raw_api(
        self, client: TestClient
    ) -> None:
        embed_response = MagicMock()
        embed_response.status_code = 200
        embed_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        embed_response.raise_for_status = MagicMock()

        mock_server = MagicMock()
        mock_server._make_request.side_effect = [
            {"id": "12345678-1234-5678-1234-567812345678"},
            {
                "ids": [["chunk-1"]],
                "documents": [["def foo(): pass"]],
                "metadatas": [[{"repo": "myrepo", "file_path": "a.py"}]],
                "distances": [[0.12]],
            },
        ]
        gateway_main._chroma._server = mock_server
        gateway_main._chroma.tenant = "default_tenant"
        gateway_main._chroma.database = "default_database"

        with patch.object(
            gateway_main._http, "post", return_value=embed_response
        ):
            resp = client.post(
                "/search",
                json={"query": "foo", "repo": "myrepo", "top_k": 3},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["results"][0]["id"] == "chunk-1"
        assert data["results"][0]["content"] == "def foo(): pass"
        assert mock_server._make_request.call_count == 2


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
