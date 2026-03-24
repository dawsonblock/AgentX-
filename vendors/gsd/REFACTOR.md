# GSD Refactor: Pipeline → Task Graph

Status: active
Last-Updated: 2026-03-15

## Goal

Replace GSD's rigid Milestone → Slice → Task pipeline with a dynamic task graph. Two roles — coder (additive-only graph authority) and reviewer (full graph authority) — replace the current single-agent pipeline that pressures toward completion.

The core invariant: **the builder cannot certify its own work.** This is enforced structurally through role separation and tool availability, not just prompt instructions.

## Context

GSD currently runs a deterministic pipeline:

```
Milestone → Slices (risk-ordered) → Tasks (per slice)
Each: research → plan → execute → complete
```

The dispatch guard (`dispatch-guard.ts`) enforces sequential ordering — S02 cannot start until S01 is `[x]`. This creates completion pressure: the system won't advance until you mark things done, which incentivizes marking things done regardless of reality.

The task graph model replaces this with a freeform DAG where:
- Coders pick up queued tasks, work on them, get blocked, create subtasks, move laterally
- Reviewers periodically verify claims, accept/reject work, restructure the graph
- There is no enforced ordering — any queued task is fair game
- Blocked is a valid terminal outcome, not a pipeline stall

## What already exists (Phase 1 complete)

These files are already written and committed in the working tree:

### Graph data model
- `src/resources/extensions/gsd/graph/types.ts` — TaskNode, BlockerNode, EvidenceClass, status enums, CODER_ALLOWED_STATUSES vs TERMINAL_STATUSES
- `src/resources/extensions/gsd/graph/store.ts` — GraphStore: filesystem-backed DAG with markdown+YAML frontmatter files in `.gsd/graph/tasks/` and `.gsd/graph/blockers/`. Methods: read/write/delete/list for tasks and blockers, plus graph queries (openTasks, openBlockers, tasksByStatus, children, roots, blockerClusters, detectCycle).

### Role-specific tools
- `src/resources/extensions/gsd/graph/coder-tools.ts` — 5 tools, additive-only:
  - `graph_create_task` — create task with optional parent (validates parent exists)
  - `graph_report_blocker` — report blocker with fingerprint, auto-blocks affected tasks
  - `graph_update_task_status` — update to non-terminal states only (queued/in_progress/blocked/deferred/done_pending_review)
  - `graph_list_tasks` — list with optional status filter
  - `graph_list_blockers` — list with optional open-only filter

- `src/resources/extensions/gsd/graph/reviewer-tools.ts` — 8 tools, full authority:
  - `graph_close_task` — set terminal status (accepted/rejected/closed) with reason
  - `graph_delete_task` — permanent delete with recursive option, cleans parent references
  - `graph_reparent_task` — restructure graph, validates no cycles via descendant check
  - `graph_resolve_blocker` — resolve with evidence, auto-unblocks tasks when all blockers resolved
  - `graph_delete_blocker` — permanent delete, cleans task references, auto-unblocks
  - `graph_query` — full state dump: status breakdown, blocker clusters, pending review, cycle detection
  - `graph_list_tasks` — same as coder
  - `graph_list_blockers` — same as coder

### Role-specific system prompts
- `src/resources/extensions/gsd/prompts/system-coder.md` — coder identity, additive-only authority boundaries, completion honesty doctrine (blocked is valid, propose not ratify, stubs with accounting, evidence classes cap claims)
- `src/resources/extensions/gsd/prompts/system-reviewer.md` — reviewer identity, full graph authority, verification principles (worker summaries not primary evidence, don't rubber-stamp, don't weaken tests, evidence class enforcement, blocker triage, anti-pattern detection)

### CLI and extension wiring
- `src/cli.ts` — `--role coder|reviewer` flag (sets `GSD_ROLE` env var), `--graph-dir <path>` flag (sets `GSD_GRAPH_DIR` env var, defaults to `.gsd/graph`)
- `src/resources/extensions/gsd/index.ts` — registers role-specific tools at startup, loads role-specific system prompt in `before_agent_start` hook, blocks write/edit/bash tools for reviewer role via `tool_call` hook

### Modified existing prompts (anti-completion-pressure)
- `system.md` — replaced "you finish what you start" paragraph with completion honesty doctrine
- `execute-task.md` — added completion honesty preamble, conditional checkbox (only mark [x] if genuinely done), "false green worse than replan"
- `complete-slice.md` — reframed from "closer" to "reviewer", don't rubber-stamp, don't weaken tests
- `complete-milestone.md` — "reviewer not rubber stamp", honest incomplete > dishonest complete
- `reassess-roadmap.md` — flag claims that don't match evidence

## Phase 2: New state derivation

**Create:** `src/resources/extensions/gsd/graph-state.ts`

**Replaces:** `state.ts` (550 lines) — current `deriveState()` reads milestone/slice/task checkboxes from the roadmap.

New `deriveGraphState()` reads the filesystem graph directly:

```typescript
interface GraphState {
  tasks: TaskNode[];
  blockers: BlockerNode[];
  openTasks: TaskNode[];          // status not in [closed, accepted, rejected]
  openBlockers: BlockerNode[];    // status === "open"
  pendingReview: TaskNode[];      // status === "done_pending_review"
  blockerClusters: Map<string, BlockerNode[]>;  // grouped by fingerprint
  cycle: string[] | null;
  roots: TaskNode[];              // tasks with no parent
  statusCounts: Map<string, number>;
}
```

Simple. Reads `.gsd/graph/`, returns structured state. No checkpoint parsing.

## Phase 3: New dispatch

**Create:** `src/resources/extensions/gsd/graph-dispatch.ts`

**Replaces:** `auto-dispatch.ts` (288 lines) — current dispatch evaluates ordered rules assuming milestone/slice/task hierarchy.

The dispatch question changes from "what's the next unit in the pipeline?" to "what's available to work on?"

### Task selection (`pickNextTask`)

Priority order:
1. Tasks in `queued` status, preferring roots (breadth-first), then by creation order (oldest first)
2. Tasks in `blocked` status whose blockers are ALL resolved/wont_fix — auto-transition to `queued` and pick
3. Return null if nothing is available

### Reviewer trigger (`shouldRunReviewer`)

Threshold-based. Run reviewer when ANY of:
- `done_pending_review` count >= 3
- Open blocker count >= 5
- Any blocker cluster has 2+ instances (repeated root cause)
- Cycle detected in graph
- No queued tasks remain but open tasks exist (everything stuck)
- Configurable: `reviewerThresholds` in `.gsd/graph/config.json` (optional)

These thresholds are starting points. Tune based on actual usage.

## Phase 4: New auto-mode

**Create:** `src/resources/extensions/gsd/graph-auto.ts`

**Replaces:** `auto.ts` (2,341 lines) — current auto-mode walks the milestone/slice/task state machine with worktree management, recovery, supervision.

The new auto-mode loop is dramatically simpler:

```
loop:
  state = deriveGraphState()

  if shouldRunReviewer(state):
    spawn fresh session with --role reviewer
    reviewer examines graph, accepts/rejects/restructures
    continue

  task = pickNextTask(state)
  if task is null:
    if all tasks in terminal status: emit "all work complete", break
    if all open tasks blocked: emit "graph stuck — all tasks blocked", pause
    break

  mark task "in_progress" on disk
  build task prompt from work-task.md template
  spawn fresh session with --role coder, task prompt
  // coder may have created subtasks, blockers, updated statuses
  continue
```

Target: ~200 lines. The simplicity is intentional — the graph, not the auto-mode loop, carries the state complexity.

### Session spawning

Each iteration spawns a fresh Pi session (same as current auto-mode). The `--role` flag determines tool availability and system prompt. The session gets the task context inlined in the prompt.

### Recovery

If a coder session crashes or times out:
- The task stays `in_progress` — reviewer can see it's stuck
- Next auto-mode iteration sees it and can re-queue or skip
- No complex crash recovery state machine needed

### Activity logging

Keep `activity-log.ts`. Log each dispatch: `{ timestamp, role, taskId, sessionId, outcome }`.

## Phase 5: New per-task prompt

**Create:** `src/resources/extensions/gsd/prompts/work-task.md`

**Replaces all of these** (17 prompt files):
- `execute-task.md`, `research-milestone.md`, `research-slice.md`, `plan-milestone.md`, `plan-slice.md`, `replan-slice.md`, `complete-slice.md`, `complete-milestone.md`, `reassess-roadmap.md`, `run-uat.md`, `rewrite-docs.md`, `guided-discuss-milestone.md`, `guided-discuss-slice.md`, `guided-plan-milestone.md`, `guided-plan-slice.md`, `guided-execute-task.md`, `guided-resume-task.md`, `guided-complete-slice.md`, `guided-research-slice.md`

`work-task.md` template:

```markdown
## Task: {{taskId}} — {{scope}}

Status: {{status}} | Creator: {{creator}} | Created: {{createdAt}}
{{#if parent}}Parent: {{parent}}{{/if}}
{{#if children}}Children: {{children}}{{/if}}
{{#if blockers}}Blockers: {{blockers}}{{/if}}

{{#if graphDigest}}
### Graph Context
{{graphDigest}}
{{/if}}

---

You are a coder. Your job is to do the work described in this task's scope.

1. Read the codebase to understand the current state
2. Build what the scope describes
3. Verify your work with concrete checks (tests, commands, observable behavior)
4. Use graph tools to record what happened

**When you finish:** `graph_update_task_status` → `done_pending_review` with evidence class and evidence references.

**When you're blocked:** `graph_report_blocker` with fingerprint and file/line evidence. The task will auto-transition to `blocked`.

**When the task needs decomposition:** `graph_create_task` with parent={{taskId}} for each subtask. Update this task to `in_progress` or `deferred`.

**When you want to park this and do something else:** `graph_update_task_status` → `deferred`.

The graph tools are your interface to the task system. Do not manually edit files in `.gsd/graph/`.
```

The key difference from the current prompts: no research-then-plan-then-execute pipeline. The coder decides their own approach. The graph captures what happened.

## Phase 6: Wire into commands

**Modify:** `src/resources/extensions/gsd/commands.ts`

### `/gsd` (bare)

Current: contextual wizard with milestone/slice state.
New: show graph status summary, offer actions:
- "Start auto-mode" → `/gsd auto`
- "Run one task" → `/gsd next`
- "Run reviewer" → `/gsd review`
- "Show graph" → `/gsd status`

### `/gsd auto`

Current: calls `startAuto()` which loops through the pipeline.
New: calls `startGraphAuto()` which runs the Phase 4 loop.

### `/gsd next`

Current: executes next pipeline unit.
New: picks next available task from graph, runs one coder session.

### `/gsd review`

New command. Spawns one reviewer session against the current graph.

### `/gsd status`

Current: milestone/slice progress dashboard.
New: graph health dashboard — status breakdown, open blockers, clusters, pending review, cycle warnings. Reuse the overlay infrastructure from `dashboard-overlay.ts`.

### Commands to remove

- `/gsd queue` — no milestones to queue. Just create root tasks.
- `/gsd discuss` — the guided discussion flow is tied to milestones. Interactive mode already lets you talk to the agent.
- `/gsd skip` — no ordered pipeline to skip within.
- `/gsd steer` — overrides are tied to milestone/slice structure.

### Commands to keep as-is

- `/gsd stop` — stops auto-mode
- `/gsd pause` — pauses auto-mode (keep, but simplify — no unit-level pause)
- `/gsd history` — if it reads activity logs, keep
- `/gsd export` — if useful, keep
- `/gsd config` — setup wizard, unrelated to pipeline
- `/gsd doctor` — diagnostics, adapt to check graph health instead of pipeline state
- `/gsd prefs` — preferences, unrelated
- `/gsd hooks` — post-unit hooks, adapt to graph dispatch

## Phase 7: Delete the pipeline

Remove these modules entirely:

| File | Lines | Reason |
|------|-------|--------|
| `auto-dispatch.ts` | 288 | Rule-based dispatch assumes hierarchy |
| `auto-prompts.ts` | 880 | Prompt builders reference milestone/slice/task IDs |
| `dispatch-guard.ts` | 89 | Enforces sequential ordering |
| `roadmap-slices.ts` | 50 | Parses roadmap checkbox format |
| `guided-flow.ts` | 1,192 | Guided flow tied to milestone lifecycle |
| `state.ts` | 550 | deriveState reads milestone/slice checkboxes |
| `paths.ts` | 428 | Milestone/slice path resolution |
| `files.ts` | 1,009 | Milestone/slice file I/O, summary parsing |
| `auto-dashboard.ts` | ~200 | Dashboard shows milestone/slice progress |
| `observability-validator.ts` | ~100 | Validates against slice plan structure |

**Total: ~4,800 lines deleted.**

Delete 17 prompt files (listed in Phase 5 above). Keep: `system.md`, `system-coder.md`, `system-reviewer.md`, `work-task.md`, `discuss.md`, `worktree-merge.md`, `queue.md` (repurpose or delete), `review-migration.md` (keep if useful), `doctor-heal.md`.

Update `index.ts` to remove dead imports referencing deleted modules. The `before_agent_start` hook, tool registration, `tool_call` guard, `session_start` header, and `agent_end` hook stay — but `agent_end` changes to call graph-auto advancement instead of pipeline advancement.

Update `commands.ts` to remove dead subcommand handlers and wire new ones.

## Phase 8: Simplify worktrees

**Modify:** `worktree.ts`, `worktree-manager.ts`, `auto-worktree.ts`, `worktree-command.ts`

Current: worktrees are mandatory per-milestone on the `milestone/<MID>` branch.

New: worktrees are optional per-task isolation. A coder can request a worktree for risky or concurrent work. No mandatory worktree-per-anything.

- Remove milestone branch naming (`milestone/<MID>` → `task/<TID>` or user-chosen)
- Remove auto-worktree setup from auto-mode (was: create worktree before each milestone)
- Keep `/worktree` command for manual worktree management
- Keep merge-back functionality

This is the lowest priority phase. The graph model works without worktree changes.

## Phase 9: Update dashboard

**Create or modify:** dashboard for graph health.

Reuse `dashboard-overlay.ts` infrastructure but render graph state instead of milestone/slice progress:

```
GSD Graph Status
────────────────────────────────
Tasks:    12 total, 8 open, 2 pending review, 2 accepted
Blockers: 4 total, 3 open
Clusters: 1 repeated (fingerprint: "missing-udp-transport", 2 instances)
Cycles:   none

Open Tasks:
  T-001 [in_progress] Wire UDP transport
    T-002 [blocked]   Create SOCK_DGRAM socket
    T-003 [queued]    Replace stdio bridge
  T-004 [deferred]   SSH bootstrap cleanup

Pending Review:
  T-005 [done_pending_review] Packet codec (evidence: unit)
  T-006 [done_pending_review] Crypto layer (evidence: integration)

Open Blockers:
  B-001 [sev:3] Missing bootstrap type contract (fp: missing-bootstrap)
    affects: T-002
  B-002 [sev:2] VT oracle linkage unclear (fp: vt-oracle-linkage)
    affects: T-003
```

## Execution order

Phases should be executed in this order. Each phase is independently testable.

1. ~~Phase 1: Graph foundation~~ — **done**
2. Phase 2: `graph-state.ts` — pure function, no dependencies on old code
3. Phase 3: `graph-dispatch.ts` — depends on Phase 2, pure function
4. Phase 4: `graph-auto.ts` — depends on Phases 2-3, the new engine
5. Phase 5: `work-task.md` — just a prompt template, no code dependencies
6. Phase 6: Wire commands — connects Phases 2-5 to the CLI
7. Phase 7: Delete the pipeline — only after Phases 2-6 are working
8. Phase 8: Simplify worktrees — low priority, can be deferred
9. Phase 9: Dashboard — nice-to-have, can be deferred

**Critical path: Phases 2 → 3 → 4 → 6 → 7.** Everything else can be done in parallel or deferred.

## Files that must NOT be modified

- Everything in `packages/` (pi-coding-agent, pi-agent-core, pi-ai, pi-tui) — upstream Pi SDK
- `src/cli.ts` — already modified, done
- `src/loader.ts` — environment setup, unrelated
- `src/onboarding.ts` — auth setup, unrelated
- `src/resource-loader.ts` — extension discovery, unrelated

## Testing

- Graph store already has tests (14 passing in agentic-framework, port them)
- `graph-state.ts` — unit test: create temp graph dir, write tasks/blockers, verify derived state
- `graph-dispatch.ts` — unit test: given a graph state, verify correct task selection and reviewer trigger
- `graph-auto.ts` — integration test: mock session spawning, verify loop behavior with various graph states
- Tool tests: verify coder can't use terminal statuses, reviewer can't use write/edit/bash

## Anti-patterns to watch for during implementation

- Do not reintroduce ordered dispatch. If you catch yourself writing "check if previous task is done before dispatching next" — stop. The graph model explicitly rejects this.
- Do not weaken the role boundary. If you catch yourself giving coders a "just this once" ability to close tasks — stop.
- Do not add complexity to the auto-mode loop. If `graph-auto.ts` exceeds 300 lines, something is wrong.
- Do not carry over milestone/slice concepts under new names. There are no "phases" or "stages" in the graph model.
- Do not make the reviewer a perpetual always-on process. It runs on threshold triggers, not continuously.
