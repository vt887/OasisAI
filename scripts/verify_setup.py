#!/usr/bin/env python3
"""OasisAI MVP - System Verification Checklist.

Run this script to verify that required components are installed and
correctly configured on the host system.
"""

from __future__ import annotations

import sys
from pathlib import Path


def check_file_exists(path: str, description: str) -> bool:
    """Check if a file exists."""
    exists = Path(path).exists()
    status = "[OK]" if exists else "[ERROR]"
    print(f"{status} {description}: {path}")
    return exists


def check_directory_exists(path: str, description: str) -> bool:
    """Check if a directory exists."""
    exists = Path(path).is_dir()
    status = "[OK]" if exists else "[ERROR]"
    print(f"{status} {description}: {path}")
    return exists


def check_file_contains(path: str, content: str, description: str) -> bool:
    """Check if a file contains specific content."""
    if not Path(path).exists():
        print(f"[ERROR] File not found: {path}")
        return False
    try:
        with open(path) as f:
            file_content = f.read()
        found = content in file_content
        status = "[OK]" if found else "[ERROR]"
        print(f"{status} {description}")
        return found
    except Exception as e:
        print(f"[ERROR] Error checking {path}: {e}")
        return False


def main() -> int:
    """Run all verification checks."""
    print("=" * 60)
    print("OasisAI MVP - System Verification Checklist")
    print("=" * 60)
    print()

    checks_passed = 0
    checks_total = 0

    # Core services
    print("CORE SERVICES")
    print("-" * 60)
    for service in ["gateway", "llm", "indexer", "graph", "agent"]:
        checks_total += 1
        if check_directory_exists(
            f"services/oasis-{service}", f"{service} service"
        ):
            checks_passed += 1
    print()

    # Modified files
    print("MODIFIED FILES (ChromaDB Integration)")
    print("-" * 60)
    modified_files = [
        (
            "services/oasis-indexer/pipeline.py",
            "chromadb",
            "Indexer uses ChromaDB",
        ),
        (
            "services/oasis-gateway/main.py",
            "chromadb",
            "Gateway uses ChromaDB",
        ),
        ("services/oasis-agent/agent.py", "chromadb", "Agent uses ChromaDB"),
        (
            "docker/docker-compose.yml",
            "CHROMA_HOST",
            "Docker-compose configured",
        ),
    ]
    for filepath, content, desc in modified_files:
        checks_total += 1
        if check_file_contains(filepath, content, desc):
            checks_passed += 1
    print()

    # Requirements
    print("REQUIREMENTS FILES")
    print("-" * 60)
    req_files = [
        "services/oasis-gateway/requirements.txt",
        "services/oasis-indexer/requirements.txt",
        "services/oasis-agent/requirements.txt",
        "services/oasis-llm/requirements.txt",
        "services/oasis-graph/requirements.txt",
    ]
    for req_file in req_files:
        checks_total += 1
        if check_file_exists(
            req_file, f"Requirements: {req_file.split('/')[1]}"
        ):
            checks_passed += 1
    print()

    # Sample application
    print("SAMPLE APPLICATION")
    print("-" * 60)
    sample_files = [
        "repos/sample-app/utils.py",
        "repos/sample-app/models.py",
        "repos/sample-app/config.py",
        "repos/sample-app/services.py",
        "repos/sample-app/errors.py",
        "repos/sample-app/main.py",
    ]
    for sample_file in sample_files:
        checks_total += 1
        if check_file_exists(sample_file, f"Sample: {Path(sample_file).name}"):
            checks_passed += 1
    print()

    # Developer tools
    print("DEVELOPER TOOLS")
    print("-" * 60)
    dev_files = [
        ("start.sh", "Startup script"),
        ("validate.py", "Validation script"),
    ]
    for dev_file, desc in dev_files:
        checks_total += 1
        if check_file_exists(dev_file, desc):
            checks_passed += 1
    print()

    # Documentation
    print("DOCUMENTATION")
    print("-" * 60)
    doc_files = [
        ("README.md", "Main README"),
        ("QUICK_START.md", "Quick start guide"),
        ("DEVELOPMENT.md", "Development guide"),
        ("UPGRADE_SUMMARY.md", "Upgrade details"),
        ("COMPLETION.md", "Completion checklist"),
        ("FILES_MANIFEST.md", "Files manifest"),
        ("EXECUTIVE_SUMMARY.md", "Executive summary"),
    ]
    for doc_file, desc in doc_files:
        checks_total += 1
        if check_file_exists(doc_file, desc):
            checks_passed += 1
    print()

    # Tests
    print("TESTS")
    print("-" * 60)
    checks_total += 1
    if check_file_exists("tests/test_integration.py", "Integration tests"):
        checks_passed += 1
    print()

    # Docker configuration
    print("DOCKER CONFIGURATION")
    print("-" * 60)
    checks_total += 1
    if check_file_exists("compose/docker-compose.yml", "Docker Compose"):
        checks_passed += 1
    print()

    # Summary
    print("=" * 60)
    print(f"[OK] Checks Passed: {checks_passed}/{checks_total}")
    print("=" * 60)
    print()

    if checks_passed == checks_total:
        print("[OK] ALL CHECKS PASSED!")
        print()
        print("Next steps:")
        print("  1. chmod +x start.sh")
        print("  2. ./start.sh")
        print("  3. python validate.py")
        print()
        return 0
    else:
        print(f"[WARN] {checks_total - checks_passed} check(s) failed")
        print()
        print("Please review the failed checks above.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
