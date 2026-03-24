# 🚀 Product: Bounded Coding Workspace

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/TypeScript-5.0+-3178C6.svg?logo=typescript&logoColor=white" alt="TypeScript 5.0+">
  <img src="https://img.shields.io/badge/FastAPI-0.109+-009688.svg?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-16+-336791.svg?logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white" alt="Docker Compose">
</p>

<p align="center">
  <b>Controlled AI-assisted code modification with supervised execution boundaries</b>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#api-reference">API</a> •
  <a href="#security-model">Security</a> •
  <a href="#development">Development</a>
</p>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Core Concepts](#core-concepts)
- [API Reference](#api-reference)
- [Security Model](#security-model)
- [Development](#development)
- [Deployment](#deployment)
- [Contributing](#contributing)

---

## 🎯 Overview

**Product** is a production-grade system for AI-assisted code modification that enforces strict boundaries between AI workers and your codebase. Unlike autonomous coding agents that operate with broad permissions, Product implements a **supervised execution model** where:

- 🔒 **All side effects flow through a policy-enforced executor**
- 📝 **Every operation is logged to an append-only event ledger**
- ✅ **All code changes require explicit human approval**
- 🧪 **CI gates block promotion of failing changes**
- 🔍 **Complete provenance tracking for auditability**

### Key Features

| Feature | Description |
|---------|-------------|
| **🔐 Runtime Sovereignty** | Single source of truth for all operational state |
| **📊 Event Ledger** | Immutable, append-only log of all system events |
| **🛡️ Policy Engine** | Fine-grained tool allowlisting and constraints |
| **🏗️ Worktree Isolation** | Each run gets an isolated git worktree |
| **🧠 Bounded Context** | Smart retrieval limits context to relevant code |
| **✅ Approval Flow** | Human-in-the-loop for all code changes |
| **🔄 CI Integration** | Automated testing and security scanning |
| **📈 Provenance** | Full traceability from task to committed code |

### Use Cases

- **🐛 Fix Failing Tests** - Isolate, diagnose, and repair test failures
- **🔧 Refactoring** - Controlled structural code improvements
- **📚 Documentation** - Generate and update code documentation
- **🆘 Bug Fixes** - Traceable, reviewed bug resolution
- **⚡ Performance** - Optimizations with validation gates

---

## 🚀 Quick Start

### Prerequisites

- **Docker** 24.0+ & **Docker Compose** 2.0+
- **Python** 3.11+ (for local development)
- **Node.js** 20+ (for UI development)
- **Git** 2.40+

### Option 1: Docker Compose (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd product

# Start the full stack
docker-compose -f product/infra/compose/docker-compose.yml up -d

# Verify services
curl http://localhost:8000/health
curl http://localhost:8001/health
```

**Services:**
| Service | URL | Description |
|---------|-----|-------------|
| Runtime API | http://localhost:8000 | Core API & event ledger |
| Open WebUI | http://localhost:3000 | Web interface |
| PostgreSQL | localhost:5432 | Event & state storage |
| CodeGraph | http://localhost:8001 | Structural code analysis |

### Option 2: Local Development

```bash
# 1. Setup database
docker run -d --name product-postgres \
  -e POSTGRES_USER=product \
  -e POSTGRES_PASSWORD=product \
  -e POSTGRES_DB=product_runtime \
  -p 5432:5432 postgres:16-alpine

# 2. Install Python dependencies
cd product/runtime
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Run database migrations
alembic upgrade head

# 4. Start runtime API
uvicorn api.main:app --reload --port 8000

# 5. In another terminal, start CodeGraph service
cd product/retrieval/codegraph_service
uvicorn app:app --reload --port 8001
```

### Create Your First Run

```bash
# Create a run
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -H "X-User-Id: developer@example.com" \
  -d '{
    "repo_id": "my-project",
    "task_type": "fix_failing_test",
    "goal": "Fix the failing payment validation test in test_payment.py",
    "constraints": {
      "network": false,
      "approval_required_for_patch_apply": true,
      "max_steps": 50
    },
    "worker_profile": "gsd-default"
  }'

# Response:
# {
#   "run_id": "550e8400-e29b-41d4-a716-446655440000",
#   "state": "created"
# }

# Check run status
curl http://localhost:8000/runs/550e8400-e29b-41d4-a716-446655440000

# View events
curl http://localhost:8000/events/run/550e8400-e29b-41d4-a716-446655440000
```

---

## 🏗️ Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Open WebUI + Extensions                       │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │   │
│  │  │ Run List │  │ Run Detail│  │ Patch Diff│  │ Approval Controls │    │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ HTTP/WebSocket
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               RUNTIME (Sovereign)                            │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         FastAPI + PostgreSQL                           │  │
│  │                                                                        │  │
│  │   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐       │  │
│  │   │  Runs    │◄──►│  Events  │◄──►│ Executor │◄──►│  Policy  │       │  │
│  │   │ Service  │    │  Store   │    │  Broker  │    │ Engine   │       │  │
│  │   └──────────┘    └──────────┘    └────┬─────┘    └──────────┘       │  │
│  │                                        │                              │  │
│  │   ┌──────────┐    ┌──────────┐        │    ┌──────────┐             │  │
│  │   │ Patches  │    │Approvals │◄───────┘    │ Artifacts│             │  │
│  │   │ Service  │    │ Service  │             │ Service  │             │  │
│  │   └──────────┘    └──────────┘             └──────────┘             │  │
│  │                                                                        │  │
│  │   [Append-Only Event Ledger] ─────────────────────────────────────►   │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
              ▼                   ▼                   ▼
┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
│   ORCHESTRATOR    │  │     WORKERS       │  │    RETRIEVAL      │
│   ┌───────────┐   │  │   ┌───────────┐   │  │   ┌───────────┐   │
│   │ Worktree  │   │  │   │   GSD     │   │  │   │ CodeGraph │   │
│   │ Adapter   │   │  │   │  Wrapper  │   │  │   │  Service  │   │
│   └───────────┘   │  │   └───────────┘   │  │   └───────────┘   │
│   ┌───────────┐   │  │   ┌───────────┐   │  │   ┌───────────┐   │
│   │  Session  │   │  │   │  Tool     │   │  │   │ Context   │   │
│   │  Manager  │   │  │   │  Bridge   │   │  │   │  Packer   │   │
│   └───────────┘   │  │   └───────────┘   │  │   └───────────┘   │
└───────────────────┘  └───────────────────┘  └───────────────────┘
```

### Authority Boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│                     RUNTIME (Sovereign Authority)                │
│  • Event ledger is the single source of truth                    │
│  • All state transitions logged immutably                        │
│  • Executor is the only path for side effects                    │
│  • Policy engine enforces all constraints                        │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Uses for state / delegates execution
┌─────────────────────────────┼───────────────────────────────────┐
│           COMPONENTS        │                                   │
│  ┌─────────┐ ┌─────────┐   │    ┌─────────┐ ┌─────────┐        │
│  │   UI    │ │Orchestr.│◄──┘    │ Workers │ │Retrieval│        │
│  │ (Shell) │ │(Adapter)│         │(Wrapper)│ │(Pipeline│        │
│  └─────────┘ └─────────┘         └─────────┘ └─────────┘        │
│                                                                 │
│  Rule: Components MAY NOT mutate state directly                 │
│  Rule: Components MUST route through Runtime executor           │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Authority |
|-----------|---------------|-----------|
| **Runtime** | Event ledger, state machine, policy enforcement, execution | ✅ Sovereign |
| **UI** | Display runs, submit approvals, view artifacts | ❌ Shell only |
| **Orchestrator** | Worktree allocation, session lifecycle | ❌ Adapter only |
| **Workers** | Request tools, propose patches | ❌ No direct mutation |
| **Retrieval** | Build bounded context, rank files | ❌ No execution |
| **Provenance** | Record trace metadata | ❌ No execution |

---

## 📚 Core Concepts

### Run Lifecycle

A **Run** represents a single coding task from creation to completion:

```
┌─────────┐    ┌─────────┐    ┌─────────────┐    ┌──────────────┐
│ CREATED │───►│ QUEUED  │───►│PROVISIONING │───►│CONTEXT_BUILD │
└─────────┘    └─────────┘    └─────────────┘    └──────┬───────┘
                                                        │
┌─────────────┐    ┌─────────────┐    ┌────────┐       │
│   FAILED    │◄───┤   PAUSED    │◄───┤RUNNING │◄──────┘
└─────────────┘    └──────┬──────┘    └───┬────┘
                          │               │
┌─────────────┐    ┌──────┴──────┐        │
│  COMPLETED  │◄───┤WAITING_APPRV│◄───────┘
└─────────────┘    └──────┬──────┘
                          │
                   ┌──────┴──────┐
                   │  CANCELLED  │
                   └─────────────┘
```

**State Descriptions:**

| State | Description |
|-------|-------------|
| `created` | Run initialized, waiting to be queued |
| `queued` | Waiting for available worker slot |
| `provisioning` | Allocating worktree and resources |
| `context_building` | Retrieving and ranking relevant code |
| `running` | Worker executing, requesting tools |
| `waiting_approval` | Patch proposed, awaiting human review |
| `paused` | Temporarily suspended |
| `completed` | Task finished successfully |
| `failed` | Task failed or error occurred |
| `cancelled` | Manually cancelled |

### Event Ledger

The event ledger is an **append-only, immutable log** of all system events:

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440001",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "seq": 17,
  "type": "ToolFinished",
  "timestamp": "2026-03-24T20:00:00Z",
  "actor": {
    "kind": "runtime",
    "id": "executor"
  },
  "payload": {
    "tool": "test.run",
    "exit_code": 1,
    "duration_ms": 1387
  }
}
```

**Guarantees:**
- ✅ Monotonically increasing sequence numbers per run
- ✅ No in-place mutation
- ✅ Immutable history
- ✅ Runtime is the only writer of operational events

### Policy Enforcement

The policy engine enforces hard boundaries on worker execution:

```python
# Example constraint configuration
constraints = {
    "network": false,                    # No network access
    "approval_required_for_patch_apply": true,  # Require approval
    "max_steps": 100,                    # Step budget
    "max_duration_seconds": 3600,        # Timeout
    "writable_paths": [                  # Allowlisted paths
        "/var/lib/product/worktrees/{run_id}/"
    ],
    "allowed_tools": [                   # Tool allowlist
        "file.read",
        "search.text", 
        "test.run",
        "git.diff"
    ]
}
```

### Worktree Isolation

Each run receives an **isolated git worktree**:

```
/var/lib/product/worktrees/
├── 550e8400-e29b-41d4-a716-446655440000/  # Run worktree
│   ├── .git/                              # Git metadata
│   ├── src/
│   ├── tests/
│   └── ...
├── 6ba7b810-9dad-11d1-80b4-00c04fd430c8/  # Another run
└── ...
```

Branch naming: `product/run-{short_uuid}-{task_type}`

### Bounded Context

The retrieval pipeline builds focused context for the worker:

```
┌─────────────────────────────────────────────────────────────┐
│                    RETRIEVAL PIPELINE                        │
│                                                              │
│  1. STRUCTURAL ANALYSIS (CodeGraphContext)                   │
│     └─► Parse AST, build call graph, find related files      │
│                                                              │
│  2. RANKING (Contextrie + Fallback)                         │
│     └─► Score by: test overlap, symbol hits, proximity       │
│                                                              │
│  3. PACKING                                                 │
│     └─► Select items within token budget, build context      │
│                                                              │
│  Output: Bounded context pack for worker consumption        │
└─────────────────────────────────────────────────────────────┘
```

---

## 📡 API Reference

### Authentication

All API requests require a `X-User-Id` header:

```bash
curl -H "X-User-Id: user@example.com" http://localhost:8000/runs
```

### Runs API

#### Create Run

```http
POST /runs
Content-Type: application/json
X-User-Id: user@example.com

{
  "repo_id": "my-project",
  "task_type": "fix_failing_test",
  "goal": "Fix failing test in payment service",
  "constraints": {
    "network": false,
    "approval_required_for_patch_apply": true,
    "max_steps": 100
  },
  "worker_profile": "gsd-default"
}
```

**Response:**
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "created"
}
```

#### Get Run

```http
GET /runs/{run_id}
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "repo_id": "my-project",
  "task_type": "fix_failing_test",
  "goal": "Fix failing test in payment service",
  "state": "running",
  "worker_profile": "gsd-default",
  "constraints": {
    "network": false,
    "approval_required_for_patch_apply": true
  },
  "created_at": "2026-03-24T20:00:00Z",
  "updated_at": "2026-03-24T20:05:00Z"
}
```

#### List Runs

```http
GET /runs?repo_id=my-project&state=running&limit=10
```

#### Cancel Run

```http
POST /runs/{run_id}/cancel
Content-Type: application/json

{
  "reason": "No longer needed"
}
```

#### Resume Run

```http
POST /runs/{run_id}/resume
Content-Type: application/json

{
  "from_step": 15
}
```

### Events API

#### Get Run Events

```http
GET /events/run/{run_id}?after_seq=10&limit=100
```

**Response:**
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "events": [
    {
      "event_id": "...",
      "seq": 11,
      "type": "ToolStarted",
      "timestamp": "2026-03-24T20:01:00Z",
      "actor": {"kind": "worker", "id": "gsd-..."},
      "payload": {"tool": "file.read", "args": {"path": "src/payment.py"}}
    },
    {
      "event_id": "...",
      "seq": 12,
      "type": "ToolFinished",
      "timestamp": "2026-03-24T20:01:01Z",
      "actor": {"kind": "runtime", "id": "executor"},
      "payload": {"tool": "file.read", "exit_code": 0}
    }
  ],
  "count": 2
}
```

### Patches API

#### Get Run Patches

```http
GET /patches/run/{run_id}
```

#### Get Patch Diff

```http
GET /patches/{patch_id}/diff
```

**Response:**
```diff
diff --git a/src/payment.py b/src/payment.py
index 1234567..abcdefg 100644
--- a/src/payment.py
+++ b/src/payment.py
@@ -45,7 +45,7 @@ def process_payment(amount, currency):
     if amount <= 0:
         raise ValueError("Amount must be positive")
     
-    if currency not in SUPPORTED_CURRENCIES:
+    if currency.upper() not in SUPPORTED_CURRENCIES:
         raise ValueError(f"Unsupported currency: {currency}")
     
     return _process_valid_payment(amount, currency)
```

### Approvals API

#### Submit Approval

```http
POST /approvals/run/{run_id}/patch/{patch_id}
Content-Type: application/json
X-User-Id: reviewer@example.com

{
  "decision": "approve",
  "reason": "Fix looks correct, addresses the root cause"
}
```

**Response:**
```json
{
  "approval_id": "...",
  "run_id": "...",
  "patch_id": "...",
  "decision": "approve",
  "actor_id": "reviewer@example.com",
  "created_at": "2026-03-24T20:10:00Z"
}
```

---

## 🔒 Security Model

### Threat Model

| Threat | Mitigation |
|--------|-----------|
| **Unauthorized code changes** | All patches require approval; policy engine enforces boundaries |
| **Data exfiltration** | Network disabled by default; read-only filesystem access |
| **Prompt injection** | Bounded context limits information exposure |
| **Supply chain attacks** | CI gates with dependency scanning (Snyk) |
| **Audit gaps** | Complete event ledger + provenance records |

### Tool Allowlist (v1)

Only these tools are available to workers:

| Tool | Description |
|------|-------------|
| `file.read` | Read file contents |
| `file.read_batch` | Read multiple files |
| `search.text` | Text search in repo |
| `search.symbol` | Symbol search |
| `git.status` | Git status |
| `git.diff` | Git diff |
| `test.run` | Run tests |
| `lint.run` | Run linter |
| `typecheck.run` | Run type checker |
| `patch.apply_candidate` | Apply patch candidate (requires approval) |

### Explicitly Blocked

- ❌ Free-form shell execution
- ❌ Arbitrary network access
- ❌ Package installation
- ❌ Direct git push/merge
- ❌ Arbitrary file writes

### Approval Requirements

| Action | Requires Approval |
|--------|------------------|
| Tool execution | No (policy-checked) |
| Patch proposal | No |
| Patch application | **Yes** |
| Promotion to main | **Yes** + CI pass |

---

## 🛠️ Development

### Project Structure

```
product/
├── runtime/                    # Core runtime (Python)
│   ├── api/                   # FastAPI routes
│   ├── runs/                  # Run lifecycle
│   ├── events/                # Event store
│   ├── executor/              # Tool execution
│   ├── policy/                # Policy engine
│   └── alembic/               # Database migrations
├── orchestrator/              # Worktree adapter (TypeScript)
│   └── adapter/
├── workers/                   # GSD wrapper (Python)
│   └── gsd_wrapper/
├── retrieval/                 # Context building
│   ├── codegraph_service/     # Structural analysis
│   └── context_packer/        # Context ranking (TypeScript)
├── provenance/                # Trace writing
│   └── trace_writer/
├── ui/                        # UI extensions
├── ci/                        # GitHub Actions
├── infra/                     # Docker, Compose
└── docs/                      # Documentation
```

### Running Tests

```bash
# Python tests
cd product/runtime
pytest -v

# TypeScript build
cd product/orchestrator/adapter
npm install
npm run build
```

### Adding a New Tool

1. **Implement in executor:**
```python
# product/runtime/executor/tools.py
def my_new_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    # Implementation
    return {"exit_code": 0, "result": ...}

TOOL_MAP["my.new_tool"] = my_new_tool
```

2. **Add to policy allowlist:**
```python
# product/runtime/policy/engine.py
DEFAULT_ALLOWED_TOOLS = {
    # ... existing tools
    "my.new_tool",
}
```

3. **Expose to worker:**
```python
# product/workers/gsd_wrapper/tool_bridge.py
def my_new_tool(self, arg: str) -> Dict[str, Any]:
    return self._execute_tool("my.new_tool", {"arg": arg})
```

### Database Migrations

```bash
cd product/runtime

# Create migration
alembic revision --autogenerate -m "Add new table"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 🚢 Deployment

### Production Checklist

- [ ] Use PostgreSQL 16+ with backups
- [ ] Configure `WORKTREE_ROOT` on persistent storage
- [ ] Set `RUNTIME_DATABASE_URL` with proper credentials
- [ ] Enable HTTPS/WSS for all endpoints
- [ ] Configure authentication (OAuth/SAML)
- [ ] Set up log aggregation
- [ ] Configure monitoring (Prometheus/Grafana)
- [ ] Enable Snyk for dependency scanning
- [ ] Review and tighten policy constraints
- [ ] Set up CI integration webhooks

### Docker Compose Production

```yaml
# product/infra/compose/docker-compose.prod.yml
version: '3.8'

services:
  runtime:
    image: product-runtime:latest
    environment:
      RUNTIME_DATABASE_URL: ${DATABASE_URL}
      WORKTREE_ROOT: /data/worktrees
    volumes:
      - /mnt/persistent/worktrees:/data/worktrees
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

### Kubernetes (Future)

See `docs/operations/kubernetes.md` for K8s deployment guide.

---

## 🤝 Contributing

### Development Workflow

1. **Fork and clone:**
```bash
git clone https://github.com/your-org/product.git
cd product
```

2. **Create branch:**
```bash
git checkout -b feature/your-feature
```

3. **Make changes:**
- Write tests
- Update documentation
- Follow existing code style

4. **Commit:**
```bash
git commit -m "feat: add new feature"
```

5. **Push and PR:**
```bash
git push origin feature/your-feature
```

### Code Style

- **Python:** Black formatter, 100 char line length
- **TypeScript:** Prettier, strict mode
- **Commits:** Conventional commits format

### Testing Requirements

- Unit tests for all new code
- Integration tests for API changes
- Policy engine tests for new constraints

---

## 📄 License

[MIT License](LICENSE) - See LICENSE file for details.

---

## 🙏 Acknowledgments

- **Open WebUI** - UI shell foundation
- **CodeGraphContext** - Structural code analysis
- **Agent Orchestrator** - Session supervision primitives
- **GSD** - Worker capabilities

---

<p align="center">
  Built with ❤️ for safe AI-assisted development
</p>
