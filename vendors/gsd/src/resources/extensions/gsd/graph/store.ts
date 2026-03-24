import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync, unlinkSync } from "node:fs";
import { join } from "node:path";
import type { TaskNode, BlockerNode } from "./types.js";

// Minimal YAML frontmatter parser/serializer — no dependency needed.

function parseFrontmatter(content: string): { meta: Record<string, unknown>; body: string } {
  const match = content.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!match) return { meta: {}, body: content };

  const meta: Record<string, unknown> = {};
  for (const line of match[1].split("\n")) {
    const idx = line.indexOf(":");
    if (idx === -1) continue;
    const key = line.slice(0, idx).trim();
    let val: unknown = line.slice(idx + 1).trim();

    if (typeof val === "string" && val.startsWith("[") && val.endsWith("]")) {
      val = val.slice(1, -1).split(",").map((s) => s.trim()).filter(Boolean);
    } else if (typeof val === "string" && /^\d+$/.test(val)) {
      val = parseInt(val, 10);
    } else if (val === "true") val = true;
    else if (val === "false") val = false;

    meta[key] = val;
  }
  return { meta, body: match[2] };
}

function serializeArray(arr: string[]): string {
  if (arr.length === 0) return "[]";
  return `[${arr.join(", ")}]`;
}

function taskToFile(task: TaskNode): string {
  return `---
id: ${task.id}
status: ${task.status}
scope: ${task.scope}
creator: ${task.creator}
created_at: ${task.createdAt}
updated_at: ${task.updatedAt}
parent: ${task.parent ?? ""}
children: ${serializeArray(task.children)}
blocked_by: ${serializeArray(task.blockedBy)}
blockers: ${serializeArray(task.blockers)}
evidence_class: ${task.evidenceClass ?? ""}
evidence: ${serializeArray(task.evidence ?? [])}
known_gaps: ${serializeArray(task.knownGaps ?? [])}
commit_refs: ${serializeArray(task.commitRefs ?? [])}
---
`;
}

function fileToTask(content: string): TaskNode {
  const { meta } = parseFrontmatter(content);
  return {
    id: String(meta.id ?? ""),
    status: String(meta.status ?? "queued") as TaskNode["status"],
    scope: String(meta.scope ?? ""),
    creator: String(meta.creator ?? ""),
    createdAt: String(meta.created_at ?? ""),
    updatedAt: String(meta.updated_at ?? ""),
    parent: meta.parent ? String(meta.parent) : undefined,
    children: Array.isArray(meta.children) ? meta.children.map(String) : [],
    blockedBy: Array.isArray(meta.blocked_by) ? meta.blocked_by.map(String) : [],
    blockers: Array.isArray(meta.blockers) ? meta.blockers.map(String) : [],
    evidenceClass: meta.evidence_class ? String(meta.evidence_class) as TaskNode["evidenceClass"] : undefined,
    evidence: Array.isArray(meta.evidence) ? meta.evidence.map(String) : [],
    knownGaps: Array.isArray(meta.known_gaps) ? meta.known_gaps.map(String) : [],
    commitRefs: Array.isArray(meta.commit_refs) ? meta.commit_refs.map(String) : [],
  };
}

function blockerToFile(b: BlockerNode): string {
  return `---
id: ${b.id}
severity: ${b.severity}
status: ${b.status}
creator: ${b.creator}
created_at: ${b.createdAt}
fingerprint: ${b.fingerprint}
affected_tasks: ${serializeArray(b.affectedTasks)}
retryable: ${b.retryable}
---

## ${b.summary}

### What was attempted
${b.whatWasAttempted}

### What failed
${b.whatFailed}

### Evidence
${b.evidence.map((e) => `- ${e}`).join("\n")}

### Suggested next action
${b.suggestedNextAction}
`;
}

function fileToBlocker(content: string): BlockerNode {
  const { meta, body } = parseFrontmatter(content);

  const sections = new Map<string, string>();
  let current = "";
  for (const line of body.split("\n")) {
    const heading = line.match(/^###\s+(.+)/);
    if (heading) {
      current = heading[1].toLowerCase().trim();
    } else if (current) {
      sections.set(current, ((sections.get(current) ?? "") + "\n" + line).trim());
    }
  }

  const summary = body.match(/^##\s+(.+)/m)?.[1] ?? "";
  const evidenceLines = (sections.get("evidence") ?? "")
    .split("\n")
    .filter((l) => l.startsWith("- "))
    .map((l) => l.slice(2));

  return {
    id: String(meta.id ?? ""),
    severity: Number(meta.severity ?? 2) as BlockerNode["severity"],
    status: String(meta.status ?? "open") as BlockerNode["status"],
    creator: String(meta.creator ?? ""),
    createdAt: String(meta.created_at ?? ""),
    fingerprint: String(meta.fingerprint ?? ""),
    affectedTasks: Array.isArray(meta.affected_tasks) ? meta.affected_tasks.map(String) : [],
    retryable: meta.retryable === true || meta.retryable === "true",
    summary,
    whatWasAttempted: sections.get("what was attempted") ?? "",
    whatFailed: sections.get("what failed") ?? "",
    evidence: evidenceLines,
    suggestedNextAction: sections.get("suggested next action") ?? "",
  };
}

export class GraphStore {
  private tasksDir: string;
  private blockersDir: string;

  constructor(graphDir: string) {
    this.tasksDir = join(graphDir, "tasks");
    this.blockersDir = join(graphDir, "blockers");
    mkdirSync(this.tasksDir, { recursive: true });
    mkdirSync(this.blockersDir, { recursive: true });
  }

  // --- Tasks ---

  writeTask(task: TaskNode): void {
    writeFileSync(join(this.tasksDir, `${task.id}.md`), taskToFile(task));
  }

  readTask(id: string): TaskNode | null {
    const path = join(this.tasksDir, `${id}.md`);
    if (!existsSync(path)) return null;
    return fileToTask(readFileSync(path, "utf-8"));
  }

  deleteTask(id: string): boolean {
    const path = join(this.tasksDir, `${id}.md`);
    if (!existsSync(path)) return false;
    unlinkSync(path);
    return true;
  }

  listTasks(): TaskNode[] {
    if (!existsSync(this.tasksDir)) return [];
    return readdirSync(this.tasksDir)
      .filter((f) => f.endsWith(".md"))
      .map((f) => fileToTask(readFileSync(join(this.tasksDir, f), "utf-8")));
  }

  // --- Blockers ---

  writeBlocker(blocker: BlockerNode): void {
    writeFileSync(join(this.blockersDir, `${blocker.id}.md`), blockerToFile(blocker));
  }

  readBlocker(id: string): BlockerNode | null {
    const path = join(this.blockersDir, `${id}.md`);
    if (!existsSync(path)) return null;
    return fileToBlocker(readFileSync(path, "utf-8"));
  }

  deleteBlocker(id: string): boolean {
    const path = join(this.blockersDir, `${id}.md`);
    if (!existsSync(path)) return false;
    unlinkSync(path);
    return true;
  }

  listBlockers(): BlockerNode[] {
    if (!existsSync(this.blockersDir)) return [];
    return readdirSync(this.blockersDir)
      .filter((f) => f.endsWith(".md"))
      .map((f) => fileToBlocker(readFileSync(join(this.blockersDir, f), "utf-8")));
  }

  // --- Graph queries ---

  openBlockers(): BlockerNode[] {
    return this.listBlockers().filter((b) => b.status === "open");
  }

  openTasks(): TaskNode[] {
    return this.listTasks().filter(
      (t) => !["closed", "accepted", "rejected"].includes(t.status),
    );
  }

  tasksByStatus(status: string): TaskNode[] {
    return this.listTasks().filter((t) => t.status === status);
  }

  children(taskId: string): TaskNode[] {
    return this.listTasks().filter((t) => t.parent === taskId);
  }

  roots(): TaskNode[] {
    return this.listTasks().filter((t) => !t.parent);
  }

  blockerClusters(): Map<string, BlockerNode[]> {
    const clusters = new Map<string, BlockerNode[]>();
    for (const b of this.openBlockers()) {
      const key = b.fingerprint || b.summary;
      const list = clusters.get(key) ?? [];
      list.push(b);
      clusters.set(key, list);
    }
    return clusters;
  }

  detectCycle(): string[] | null {
    const tasks = new Map(this.listTasks().map((t) => [t.id, t]));
    const visited = new Set<string>();
    const stack = new Set<string>();

    const dfs = (id: string, path: string[]): string[] | null => {
      if (stack.has(id)) return [...path, id];
      if (visited.has(id)) return null;
      visited.add(id);
      stack.add(id);

      const task = tasks.get(id);
      if (task) {
        for (const childId of task.children) {
          const cycle = dfs(childId, [...path, id]);
          if (cycle) return cycle;
        }
        for (const blockerId of task.blockedBy) {
          if (tasks.has(blockerId)) {
            const cycle = dfs(blockerId, [...path, id]);
            if (cycle) return cycle;
          }
        }
      }

      stack.delete(id);
      return null;
    };

    for (const id of tasks.keys()) {
      const cycle = dfs(id, []);
      if (cycle) return cycle;
    }
    return null;
  }
}
