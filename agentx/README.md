# AgentX

Bounded coding workspace with LLM agents.

## Architecture

```
API → RunService → RunExecutor → Orchestrator → LLM Worker
→ PatchService → ApprovalService → CIService → Apply
```

**Single execution authority:** Only `RunExecutor` executes logic.

## Quick Start

### 1. Install

```bash
cd agentx
pip install -r requirements.txt
```

### 2. Configure

```bash
export KIMI_API_KEY="your_key_here"
```

### 3. Run

```bash
./scripts/run_dev.sh
```

### 4. Create a run

```bash
curl -X POST http://localhost:8000/runs/ \
  -H "Content-Type: application/json" \
  -d '{"task": "Fix the bug in utils.py", "repo": "./myrepo"}'
```

### 5. Approve patch

```bash
curl -X POST http://localhost:8000/approvals/{patch_id} \
  -H "Content-Type: application/json" \
  -d '{"decision": "approve"}'
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `KIMI_API_KEY` | - | Kimi API key (required) |
| `KIMI_BASE_URL` | https://api.moonshot.cn/v1 | API base URL |
| `KIMI_MODEL` | kimi-latest | Model name |
| `AGENTX_DB_URL` | sqlite:///./agentx.db | Database URL |
| `AGENTX_WORKTREE_ROOT` | ./worktrees | Worktree directory |
| `AGENTX_WORKER_MAX_STEPS` | 20 | Max worker steps |

## API Endpoints

- `POST /runs/` - Create and execute run
- `GET /runs/{run_id}` - Get run details
- `GET /runs/` - List runs
- `POST /approvals/{patch_id}` - Approve/reject patch
- `GET /patches/{patch_id}` - Get patch details
- `GET /patches/run/{run_id}` - List patches for run
- `GET /artifacts/run/{run_id}` - List artifacts

## Security

- API key loaded from environment (never hardcoded)
- Worker sandboxed to worktree
- Path traversal blocked
- Tool allowlist enforced
- Max steps limit

## License

MIT
