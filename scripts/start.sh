#!/bin/bash
# OasisAI Startup and Testing Script

set -e

echo "=================================="
echo "OasisAI MVP - Startup Script"
echo "=================================="

# Check if docker is running
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed"
    exit 1
fi

# Start the docker-compose stack
echo ""
echo "1) Starting Docker Compose stack..."
cd "$(dirname "$0")/docker"
docker-compose down 2>/dev/null || true
docker-compose up -d --build

# Wait for services to be healthy
echo ""
echo "2) Waiting for services to be healthy..."
sleep 10

# Check health endpoints
check_service() {
    local url=$1
    local name=$2
    if curl -s "$url" > /dev/null 2>&1; then
        echo "[OK] $name is healthy"
        return 0
    else
        echo "[ERROR] $name is not responding"
        return 1
    fi
}

check_service "http://localhost:8000/health" "Gateway"
check_service "http://localhost:8001/health" "LLM"
check_service "http://localhost:8002/health" "Indexer"
check_service "http://localhost:8003/health" "Graph"
check_service "http://localhost:8004/health" "Agent"

# Pull Ollama models
echo ""
echo "3) Pulling required Ollama models..."
echo "   (This may take a few minutes on first run)"
docker exec -it oasisai-ollama-1 ollama pull codellama 2>/dev/null || echo "   codellama already present"
docker exec -it oasisai-ollama-1 ollama pull nomic-embed-text 2>/dev/null || echo "   nomic-embed-text already present"

# Index the sample application
echo ""
echo "4) Indexing sample application..."
RESPONSE=$(curl -s -X POST http://localhost:8000/index \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/repos/sample-app", "repo_name": "sample-app"}')
echo "Response: $RESPONSE"

# Give indexing time to complete
sleep 5

# Test semantic search
echo ""
echo "5) Testing semantic search..."
RESPONSE=$(curl -s -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "user data validation", "top_k": 3}')
echo "Response: $RESPONSE"

# Test ask endpoint
echo ""
echo "6) Testing ask endpoint..."
RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What functions are available in the utils module?", "repo": "sample-app"}')
echo "Response: $RESPONSE"

# Test refactor endpoint
echo ""
echo "7) Testing refactor endpoint..."
RESPONSE=$(curl -s -X POST http://localhost:8000/refactor \
  -H "Content-Type: application/json" \
  -d '{"instruction": "Add type hints to all functions", "repo": "sample-app"}')
echo "Response: $RESPONSE"

echo ""
echo "[OK] All tests completed!"
echo ""
echo "=================================="
echo "Service URLs:"
echo "  Gateway:     http://localhost:8000"
echo "  LLM:         http://localhost:8001"
echo "  Indexer:     http://localhost:8002"
echo "  Graph:       http://localhost:8003"
echo "  Agent:       http://localhost:8004"
echo "  ChromaDB:    http://localhost:8000 (internal)"
echo "  Ollama:      http://localhost:11434"
echo "=================================="
