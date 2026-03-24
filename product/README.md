# Product: Bounded Coding Workspace

A controlled AI-assisted code modification system with supervised execution boundaries.

## Architecture

The system consists of these core components:

- **Runtime** (`runtime/`): The sovereign authority for runs, events, and execution
- **Orchestrator** (`orchestrator/`): Worktree allocation and session supervision
- **Workers** (`workers/`): GSD wrapper with runtime-mediated tool access
- **Retrieval** (`retrieval/`): Context building and ranking
- **Provenance** (`provenance/`): Trace writing for accountability
- **UI** (`ui/`): Open WebUI shell with product extensions

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- Node.js 20+ (for TypeScript components)

### Running with Docker Compose

```bash
cd product/infra/compose
docker-compose up -d
```

Services:
- Runtime API: http://localhost:8000
- Open WebUI: http://localhost:3000
- Postgres: localhost:5432

### Local Development

1. Install Python dependencies:
```bash
cd product/runtime
pip install -r requirements.txt
```

2. Run database migrations:
```bash
alembic upgrade head
```

3. Start the runtime:
```bash
uvicorn api.main:app --reload
```

## Using the Dashboard

A minimal web dashboard is included for easy interaction:

```bash
# Start the runtime API (in one terminal)
cd product/runtime
uvicorn api.main:app --reload

# Start the dashboard (in another terminal)
cd product/ui/simple-dashboard
python server.py
```

The dashboard will open automatically at http://localhost:8080

Features:
- Create new runs with a simple form
- View all runs with state badges
- Click a run to see details
- View event log in real-time
- View patch diffs with syntax highlighting
- Approve or reject patches with one click
- Auto-refreshes every 10 seconds

## Creating a Run (API)

```bash
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "repo_id": "my-repo",
    "task_type": "fix_failing_test",
    "goal": "Fix the failing test in payment service",
    "constraints": {
      "network": false,
      "approval_required_for_patch_apply": true
    }
  }'
```

## Project Structure

```
product/
├── runtime/              # Core runtime (Python/FastAPI)
│   ├── api/             # REST API
│   ├── runs/            # Run lifecycle
│   ├── events/          # Event store
│   ├── executor/        # Tool execution
│   └── policy/          # Policy engine
├── orchestrator/        # Worktree/session adapter
├── workers/            # GSD wrapper
├── retrieval/          # Context building
├── provenance/         # Trace writing
├── ci/                 # CI workflows
├── infra/              # Docker, Compose
└── docs/               # Documentation

vendors/                # Donor repositories
├── open-webui/
├── agent-orchestrator/
├── gsd/
├── codegraphcontext/
├── contextrie/
├── agent-trace/
└── snyk-actions/

reference/              # Reference implementations
└── rag-anything/
```

## Key Principles

1. **Runtime Sovereignty**: Runtime owns all operational truth
2. **Append-Only Events**: All changes logged to event store
3. **Hard Boundaries**: Workers cannot directly mutate filesystem
4. **Approval Gates**: Patches require explicit approval
5. **CI Integration**: Security and quality gates before promotion

## Development Phases

See `docs/architecture/phases.md` for the full development roadmap.

Current phase: Phase 2-4 (Runtime scaffold + Event store + Executor)

## Contributing

1. All side effects go through the executor
2. All state changes emit events
3. Policy engine validates all tool requests
4. Workers are contained - no direct repo access

## License

[License TBD]
