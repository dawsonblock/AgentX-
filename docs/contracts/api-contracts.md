# API Contracts

## Run Creation

### POST /runs

Create a new coding run.

**Request:**
```json
{
  "repo_id": "repo_alpha",
  "task_type": "fix_failing_test",
  "goal": "Fix failing tests in payment service",
  "constraints": {
    "network": false,
    "approval_required_for_patch_apply": true
  },
  "worker_profile": "gsd-default"
}
```

**Response:**
```json
{
  "run_id": "uuid",
  "state": "created"
}
```

## Run States

Valid states for v1:
- `created` - Initial state
- `queued` - Waiting for resources
- `provisioning` - Allocating worktree
- `context_building` - Building bounded context
- `running` - Worker executing
- `waiting_approval` - Awaiting user review
- `paused` - Temporarily stopped
- `failed` - Terminal failure state
- `completed` - Terminal success state
- `cancelled` - Terminal cancelled state

## Event Envelope

```json
{
  "event_id": "uuid",
  "run_id": "uuid",
  "seq": 17,
  "type": "ToolFinished",
  "timestamp": "2026-03-24T20:00:00Z",
  "actor": {
    "kind": "runtime",
    "id": "executor"
  },
  "payload": {}
}
```

Rules:
- Events are append-only
- Sequence numbers are monotonic per run
- No in-place mutation
- Runtime writes all operational events

## Patch Proposal

```json
{
  "patch_id": "uuid",
  "run_id": "uuid",
  "format": "unified_diff",
  "base_ref": "gitsha",
  "files": [
    {
      "path": "src/payment/service.py",
      "status": "modified"
    }
  ],
  "diff_text": "..."
}
```

## Tool Result

Every executor tool returns:

```json
{
  "tool_name": "test.run",
  "exit_code": 0,
  "stdout": "...",
  "stderr": "",
  "duration_ms": 1387,
  "files_touched": [],
  "artifacts_produced": [
    {
      "artifact_id": "uuid",
      "kind": "test_log"
    }
  ]
}
```

## API Endpoints

### Runs
- `POST /runs` - Create run
- `GET /runs` - List runs
- `GET /runs/{id}` - Get run
- `POST /runs/{id}/cancel` - Cancel run
- `POST /runs/{id}/resume` - Resume run
- `GET /runs/{id}/worktree` - Get worktree

### Events
- `GET /events/run/{run_id}` - Get run events
- `GET /events/run/{run_id}/latest` - Get latest event
- `GET /events/run/{run_id}/count` - Get event count

### Artifacts
- `GET /artifacts/run/{run_id}` - List artifacts
- `GET /artifacts/{id}` - Get artifact
- `GET /artifacts/{id}/content` - Get artifact content
- `POST /artifacts/run/{run_id}` - Upload artifact

### Patches
- `GET /patches/run/{run_id}` - Get run patches
- `GET /patches/{id}` - Get patch
- `GET /patches/{id}/diff` - Get patch diff
- `POST /patches/run/{run_id}` - Create patch

### Approvals
- `GET /approvals/run/{run_id}` - Get approvals
- `GET /approvals/{id}` - Get approval
- `POST /approvals/run/{run_id}/patch/{patch_id}` - Submit approval
