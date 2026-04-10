# OasisAI - GitHub Actions Workflows

## Overview

This directory contains automated workflows for CI/CD, testing, security, and release management.

---

## Workflows

### 1. CI (Continuous Integration)
**File:** `.github/workflows/ci.yml`
**Triggers:** Push to main/develop, Pull requests

**Jobs:**
- **Lint & Format Check** - Validates code formatting and style
  - Ruff format check
  - Ruff linting
  - MyPy type checking

- **Security Scan** - Scans for vulnerabilities
  - Trivy filesystem scan
  - Reports to GitHub Security tab

- **Build Docker** - Validates Docker images build
  - Builds all 5 services
  - Caches layers for speed

### 2. Tests
**File:** `.github/workflows/test.yml`
**Triggers:** Push to main/develop, Pull requests

**Jobs:**
- **Unit Tests**
  - Runs pytest on unit tests
  - Generates coverage report
  - Uploads to Codecov

- **Integration Tests**
  - Starts ChromaDB and Ollama services
  - Runs integration tests
  - Validates end-to-end functionality

- **Coverage Report**
  - Generates HTML coverage report
  - Uploads as artifact
  - Available for download

### 3. Security
**File:** `.github/workflows/security.yml`
**Triggers:** Push, Pull requests, Weekly schedule

**Jobs:**
- **Dependency Check**
  - Checks Poetry dependencies
  - Runs pip-audit for vulnerabilities
  - Non-blocking

- **CodeQL Analysis**
  - GitHub's static code analysis
  - Python security scanning
  - Results in Security tab

- **Trivy Scan**
  - Filesystem vulnerability scan
  - SARIF format output
  - Integration with GitHub Security

### 4. Documentation
**File:** `.github/workflows/docs.yml`
**Triggers:** Changes to .md files

**Jobs:**
- **Markdown Lint** - Validates markdown syntax
- **Spelling Check** - Checks for typos
- **Link Check** - Validates all links

### 5. Release
**File:** `.github/workflows/release.yml`
**Triggers:** Git tags matching `v*` pattern

**Jobs:**
- **Validate** - Full validation suite
  - All tests
  - Code quality
  - Type checking

- **Build & Push** - Builds and pushes Docker images
  - All 5 services
  - To GitHub Container Registry
  - Tagged with version

- **Create Release** - Creates GitHub Release
  - Automatic release notes
  - Links to Docker images
  - Test summary

---

## Workflow Triggers

### CI Workflow
```yaml
on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]
```

Runs on:
- Every push to main or develop
- Every pull request to main or develop

### Test Workflow
```yaml
on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]
```

Runs on:
- Every push to main or develop
- Every pull request to main or develop

### Security Workflow
```yaml
on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]
  schedule:
    - cron: '0 2 * * 0'  # Weekly Sunday 2 AM
```

Runs on:
- Every push to main or develop
- Every pull request to main or develop
- Weekly schedule (Sunday 2 AM UTC)

### Documentation Workflow
```yaml
on:
  push:
    branches: [ main, develop ]
    paths:
      - '**.md'
  pull_request:
    branches: [ main, develop ]
    paths:
      - '**.md'
```

Runs on:
- Changes to markdown files
- Useful for documentation-only changes

### Release Workflow
```yaml
on:
  push:
    tags:
      - 'v*'
```

Runs on:
- Any git tag matching `v*` (e.g., v1.0.0, v0.1.2)

---

## Workflow Status

View workflow status:
- In GitHub repo: **Actions** tab
- In pull requests: Status checks
- In commits: Status indicator

---

## Environment Secrets

Some workflows can use GitHub secrets:

```yaml
secrets:
  GITHUB_TOKEN         # Automatically provided
  REGISTRY_USERNAME    # For image pushes (if needed)
  REGISTRY_PASSWORD    # For image pushes (if needed)
```

---

## Docker Image Registry

Images are pushed to GitHub Container Registry (GHCR):

```
ghcr.io/yourorg/oasisai/oasis-gateway:v1.0.0
ghcr.io/yourorg/oasisai/oasis-indexer:v1.0.0
ghcr.io/yourorg/oasisai/oasis-agent:v1.0.0
ghcr.io/yourorg/oasisai/oasis-graph:v1.0.0
ghcr.io/yourorg/oasisai/oasis-llm:v1.0.0
```

---

## Creating a Release

### 1. Create a git tag
```bash
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

### 2. Release workflow starts automatically
- Validates everything
- Builds and pushes images
- Creates GitHub Release

### 3. View release
- Go to GitHub repo → Releases
- See release notes and Docker image links

---

## Caching

Workflows use GitHub Actions caching for speed:

```yaml
- uses: actions/cache@v3
  with:
    path: .venv
    key: ${{ runner.os }}-poetry-${{ hashFiles('**/poetry.lock') }}
```

Cache is restored on subsequent runs, speeding up workflows.

---

## Artifacts

Some workflows upload artifacts:

- **Coverage Report** (test.yml)
  - HTML coverage report
  - Download from Actions tab
  - Available for 90 days

---

## Status Badges

Add to README:

```markdown
[![CI](https://github.com/yourorg/oasisai/workflows/CI/badge.svg?branch=main)](https://github.com/yourorg/oasisai/actions)
[![Tests](https://github.com/yourorg/oasisai/workflows/Tests/badge.svg?branch=main)](https://github.com/yourorg/oasisai/actions)
[![Security](https://github.com/yourorg/oasisai/workflows/Security%20Scan/badge.svg?branch=main)](https://github.com/yourorg/oasisai/actions)
```

---

## Troubleshooting

### Workflow Failed
1. Click on workflow in Actions tab
2. View logs for each job
3. Look for error messages
4. Fix issues and push again

### Tests Failing in CI
```bash
# Run locally to debug
make test
make lint
```

### Docker Build Failing
```bash
# Try building locally
docker build -t oasis-gateway services/oasis-gateway/
```

---

## Performance Tips

1. **Use caching** - Already configured
2. **Conditional jobs** - Skip unnecessary jobs
3. **Parallel jobs** - Run independent jobs together
4. **Fail fast** - Stop early if critical job fails

---

## Best Practices

1. ✅ Write tests for all changes
2. ✅ Keep workflows simple and focused
3. ✅ Use caching to speed up builds
4. ✅ Test workflows locally before committing
5. ✅ Review workflow logs regularly
6. ✅ Keep dependencies updated
7. ✅ Monitor security scan results

---

## Related Documentation

- [GitHub Actions Documentation](https://docs.github.com/actions)
- [OasisAI README](../README.md)
- [Development Guide](../DEVELOPMENT.md)
- [Makefile Guide](../MAKEFILE_GUIDE.md)

---

## File Structure

```
.github/
├── workflows/
│   ├── ci.yml              # Linting, formatting, Docker build
│   ├── test.yml            # Unit and integration tests
│   ├── security.yml        # Security scanning
│   ├── docs.yml            # Documentation validation
│   └── release.yml         # Release automation
└── WORKFLOWS.md            # This file
```

---

**All workflows are automated and require no manual intervention!**

