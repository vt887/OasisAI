#!/usr/bin/env python3
"""Quick validation script to test OasisAI endpoints."""

from __future__ import annotations

import importlib
import os
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

settings = importlib.import_module("shared.config").settings

BASE_URL = os.getenv("OASIS_VALIDATE_URL", "http://localhost:8080")
TIMEOUT = float(
    os.getenv(
        "OASIS_VALIDATE_TIMEOUT",
        str(max(settings.http_client_timeout_seconds, 240.0)),
    )
)


def test_health(client: httpx.Client) -> bool:
    """Test gateway health endpoint."""
    try:
        resp = client.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        resp.raise_for_status()
        print("[OK] Gateway health check passed")
        return True
    except Exception as e:
        print(f"[ERROR] Gateway health check failed: {e}")
        return False


def test_index(client: httpx.Client) -> bool:
    """Test indexing a repository."""
    try:
        payload = {"repo_path": "/repos/sample-app", "repo_name": "sample-app"}
        resp = client.post(f"{BASE_URL}/index", json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        chunks_indexed = data.get("chunks_indexed", 0)
        print(f"[OK] Indexing passed: {chunks_indexed} chunks indexed")
        return True
    except Exception as e:
        print(f"[ERROR] Indexing failed: {e}")
        return False


def test_search(client: httpx.Client) -> bool:
    """Test semantic search."""
    try:
        payload = {"query": "user data handling", "top_k": 3}
        resp = client.post(f"{BASE_URL}/search", json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        print(f"[OK] Search passed: {len(results)} results found")
        if results:
            top_meta = results[0].get("metadata", {})
            top_path = top_meta.get("file_path", "unknown")
            print(f"   Top result: {top_path}")
        return True
    except Exception as e:
        print(f"[ERROR] Search failed: {e}")
        return False


def test_ask(client: httpx.Client) -> bool:
    """Test ask endpoint."""
    try:
        payload = {
            "question": "What is the purpose of the User class?",
            "repo": "sample-app",
            "top_k": 3,
        }
        resp = client.post(f"{BASE_URL}/ask", json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        answer = data.get("answer", "")
        sources = data.get("sources", [])
        ans_len = len(answer)
        src_len = len(sources)
        print(
            f"[OK] Ask passed: got answer ({ans_len} chars) "
            f"with {src_len} sources"
        )
        return True
    except Exception as e:
        print(f"[ERROR] Ask failed: {e}")
        return False


def test_refactor(client: httpx.Client) -> bool:
    """Test refactor endpoint."""
    try:
        payload = {
            "instruction": "Add comprehensive error handling",
            "repo": "sample-app",
            "top_k": 3,
        }
        resp = client.post(
            f"{BASE_URL}/refactor", json=payload, timeout=TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        plan = data.get("plan", "")
        patches = data.get("patches", [])
        plan_len = len(plan)
        patches_len = len(patches)
        print(
            f"[OK] Refactor passed: got plan ({plan_len} chars) "
            f"with {patches_len} patches"
        )
        return True
    except Exception as e:
        print(f"[ERROR] Refactor failed: {e}")
        return False


def main() -> int:
    """Run all tests."""
    print("=" * 50)
    print("OasisAI MVP - Validation Tests")
    print("=" * 50)
    print()

    # Wait for services to be ready
    print("Waiting for services to be ready...")
    client = httpx.Client(timeout=TIMEOUT)

    for attempt in range(10):
        try:
            client.get(f"{BASE_URL}/health")
            break
        except Exception:
            if attempt < 9:
                print(f"  Attempt {attempt + 1}/10: waiting...")
                time.sleep(2)
            else:
                print("[ERROR] Services not responding after 20 seconds")
                return 1

    print()

    # Run tests
    results = []
    results.append(("Health Check", test_health(client)))

    print()
    time.sleep(2)  # Small delay between tests

    results.append(("Indexing", test_index(client)))

    print()
    time.sleep(3)  # Give indexing time

    results.append(("Search", test_search(client)))
    results.append(("Ask", test_ask(client)))
    results.append(("Refactor", test_refactor(client)))

    # Summary
    print()
    print("=" * 50)
    print("Test Summary")
    print("=" * 50)
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[OK]" if result else "[ERROR]"
        print(f"{status} {test_name}")

    print()
    print(f"Passed: {passed}/{total}")

    client.close()
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
