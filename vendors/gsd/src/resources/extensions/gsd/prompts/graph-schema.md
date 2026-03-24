## Task Graph Schema (Injected Contract)

This schema is tool-owned context. It is injected into your system prompt.

- Graph data lives in project state under `.gsd/graph/`.
- Schema contract lives in this extension (not in project-owned docs).
- Records are plain markdown files with frontmatter.
- Keep records machine-readable and human-readable.

### Layout

```text
.gsd/graph/
  tasks/T-*.md
  blockers/B-*.md
  handoffs/H-*.md
```

### Task record

Frontmatter keys:

- `id`: `T-*`
- `status`: `queued | in_progress | blocked | done_pending_review | accepted | closed | rejected | deferred`
- `scope`: concise work statement
- `creator`: agent id
- `created_at`, `updated_at`: ISO timestamp
- `parent`: optional task id
- `children`: task id list
- `blocked_by`: id list
- `blockers`: blocker id list
- `evidence_class`: optional (`unit | simulation | smoke | integration | behavioral | production`)
- `evidence`: optional list
- `known_gaps`: optional list
- `commit_refs`: optional list

### Blocker record

Frontmatter keys:

- `id`: `B-*`
- `severity`: `1 | 2 | 3`
- `status`: `open | triaged | resolved | wont_fix`
- `creator`: agent id
- `created_at`: ISO timestamp
- `fingerprint`: deterministic root-cause key
- `affected_tasks`: task id list
- `retryable`: boolean

Body sections (required):

- `## <summary>`
- `### What was attempted`
- `### What failed`
- `### Evidence` (bullet list)
- `### Suggested next action`

### Handoff record

Frontmatter keys:

- `id`: `H-*`
- `status`: `open | acknowledged | superseded`
- `from_role`: role that was blocked
- `to_role`: role required to execute
- `creator`: agent id
- `created_at`: ISO timestamp
- `attempted_action`: blocked action summary
- `denied_operation`: short denied operation key

Body sections (required):

- `## Why blocked`
- `## Minimal handoff payload`
- `## Evidence`

### Authority boundaries

- Coder authority:
  - create tasks/subtasks
  - report blockers
  - update task status only to: `queued`, `in_progress`, `blocked`, `deferred`, `done_pending_review`
- Reviewer authority:
  - terminal task states: `accepted`, `closed`, `rejected`
  - resolve/delete blockers
  - delete/reparent tasks
  - restructure graph

### Role-lock rule

- An agent must not switch authority by assertion ("I'll act as coder now").
- An agent must not delegate to subagents to bypass role boundaries.
- Reviewers must not create/edit raw graph records via filesystem writes (`write`/`edit` on `.gsd/graph/*`).
- If role permissions prevent required work, emit a `ROLE-BOUNDARY BLOCKED` report with:
  - attempted action
  - denied tool/operation
  - required role (`coder` or `reviewer`)
  - minimal handoff payload
  - persisted handoff artifact via `graph_emit_handoff`

### Invariants

- Builder proposes done; reviewer closes done.
- Blockers must include concrete evidence and stable fingerprint.
- Stubs/TODOs require explicit blocker or known-gap accounting.
