# Product Architecture Overview

## System Overview

The Product is a bounded coding workspace that enables controlled AI-assisted code modification through a supervised execution boundary.

## Core Principles

### 1. Runtime Sovereignty

The runtime (`product/runtime/`) is the sole authority for:
- Run lifecycle and state
- Event ledger (append-only)
- Executor boundary (all side effects)
- Policy enforcement
- Patch truth
- Approval state
- Promotion handoff

### 2. Component Boundaries

| Component | May Do | May NOT Do |
|-----------|--------|------------|
| **UI** | Create runs, display status, show logs/artifacts | Mutate repos, run tools, decide state |
| **Orchestrator** | Allocate worktrees, supervise sessions | Own ledger, own patch truth |
| **Worker** | Request tools, propose patches | Direct file writes, shell execution |
| **Retrieval** | Build context, rank files | Execute code |
| **Provenance** | Record metadata | Execute code |

### 3. Event-Driven Architecture

All operational truth flows through the event log:
- Events are append-only
- Sequence numbers are monotonic per run
- No in-place mutation
- Runtime writes all operational events

## System Components

```
product/
├── runtime/          # Core runtime (Python/FastAPI)
│   ├── api/          # REST API routes
│   ├── runs/         # Run lifecycle
│   ├── events/       # Event store
│   ├── executor/     # Tool execution boundary
│   └── policy/       # Policy engine
├── orchestrator/     # Worktree/session management
│   └── adapter/      # TypeScript adapter
├── workers/          # Worker wrappers
│   └── gsd_wrapper/  # GSD containment
├── retrieval/        # Context building
│   ├── codegraph_service/
│   └── context_packer/
├── provenance/       # Trace writing
│   └── trace_writer/
└── ui/               # UI extensions
    └── extensions/
```

## Data Flow

1. **Run Creation**
   - UI → Runtime API: POST /runs
   - Runtime: Create run record, emit RunCreated

2. **Worktree Allocation**
   - Runtime → Orchestrator: allocateWorktree
   - Orchestrator: Clone repo, create branch
   - Runtime: Emit WorktreeAllocated

3. **Context Building**
   - Runtime: Call CodeGraphContext for structural candidates
   - Runtime: Call Contextrie for ranking
   - Runtime: Emit ContextBuilt

4. **Worker Execution**
   - Runtime: Start GSD wrapper with context
   - Worker: Request tools through tool bridge
   - Executor: Validate through policy, execute, emit events
   - Worker: Submit patch proposal

5. **Review & Approval**
   - UI: Display patch, logs, artifacts
   - User: Approve or reject
   - Runtime: Update approval state

6. **CI & Promotion**
   - Approved patch triggers CI
   - CI gates: lint, test, typecheck, security scan
   - On success: Promote to merge

## Run States

```
created → queued → provisioning → context_building → running
                                              ↓
waiting_approval ← paused ← running → completed
       ↓
  failed / cancelled
```

## Security Model

### Tool Allowlist
Only these tools are available in v1:
- `repo.read_tree`, `file.read`
- `search.text`, `search.symbol`
- `git.status`, `git.diff`
- `test.run`, `lint.run`, `typecheck.run`
- `patch.apply_candidate`

### Explicit Non-Goals (v1)
- No free-form shell execution
- No package installs
- No arbitrary network
- No arbitrary git push/merge
- No arbitrary file writes

### Policy Enforcement
- Network access denied by default
- Writable paths are allowlisted
- Step budgets enforced
- Approval required for patch application

## Database Schema

See `docs/architecture/schema.md` for full schema.

Core tables:
- `runs` - Run metadata and state
- `run_events` - Append-only event log
- `worktrees` - Worktree allocations
- `artifacts` - Artifact metadata
- `patches` - Patch proposals
- `approvals` - Approval decisions
- `provenance_records` - Provenance metadata
