/**
 * Reviewer tools — full authority over the task graph.
 *
 * Reviewers can close/accept/reject tasks, delete tasks and blockers,
 * reparent tasks, resolve blockers, and query full graph state.
 * Reviewers CANNOT write product code.
 */

import { Type } from "@sinclair/typebox";
import { GraphStore } from "./store.js";
import type { TaskNode } from "./types.js";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

function textResult(text: string) {
  return { content: [{ type: "text" as const, text }], details: {} };
}

export function createReviewerTools(graphDir: string, reviewerId: string) {
  const graph = new GraphStore(graphDir);
  const handoffsDir = join(graphDir, "handoffs");
  mkdirSync(handoffsDir, { recursive: true });

  const collectDescendants = (taskId: string): Set<string> => {
    const visited = new Set<string>();
    const walk = (id: string) => {
      if (visited.has(id)) return;
      visited.add(id);
      const task = graph.readTask(id);
      if (!task) return;
      for (const childId of task.children) walk(childId);
    };
    walk(taskId);
    return visited;
  };

  const closeTask = {
    name: "graph_close_task",
    label: "Close Task",
    description: "Set a task to a terminal status: accepted (work verified good), rejected (work doesn't meet requirements), or closed (no longer relevant).",
    parameters: Type.Object({
      taskId: Type.String({ description: "Task ID" }),
      status: Type.String({ description: "Terminal status: accepted | rejected | closed" }),
      reason: Type.String({ description: "Why this decision was made — cite specific evidence" }),
    }),
    async execute(_toolCallId: string, params: { taskId: string; status: string; reason: string }) {
      if (!["accepted", "rejected", "closed"].includes(params.status)) {
        return textResult(`Invalid terminal status: "${params.status}". Must be accepted, rejected, or closed.`);
      }
      const task = graph.readTask(params.taskId);
      if (!task) return textResult(`Task ${params.taskId} not found.`);

      task.status = params.status as any;
      task.updatedAt = new Date().toISOString();
      graph.writeTask(task);

      return textResult(`${params.taskId} → ${params.status}. Reason: ${params.reason}`);
    },
  };

  const deleteTask = {
    name: "graph_delete_task",
    label: "Delete Task",
    description: "Permanently delete a task from disk. Use for noise, duplicates, or dead branches. Optionally delete all children recursively.",
    parameters: Type.Object({
      taskId: Type.String({ description: "Task ID to delete" }),
      recursive: Type.Optional(Type.Boolean({ description: "Also delete all children" })),
      reason: Type.String({ description: "Why this task is being deleted" }),
    }),
    async execute(_toolCallId: string, params: { taskId: string; recursive?: boolean; reason: string }) {
      const deleted: string[] = [];

      const doDelete = (id: string) => {
        const task = graph.readTask(id);
        if (!task) return;
        if (params.recursive) {
          for (const childId of task.children) doDelete(childId);
        }
        // Remove from parent's children list
        if (task.parent) {
          const parent = graph.readTask(task.parent);
          if (parent) {
            parent.children = parent.children.filter(c => c !== id);
            parent.updatedAt = new Date().toISOString();
            graph.writeTask(parent);
          }
        }
        graph.deleteTask(id);
        deleted.push(id);
      };

      doDelete(params.taskId);
      return textResult(`Deleted ${deleted.length} task(s): ${deleted.join(", ")}. Reason: ${params.reason}`);
    },
  };

  const reparentTask = {
    name: "graph_reparent_task",
    label: "Reparent Task",
    description: "Move a task to a different parent, or make it a root task. Use when the decomposition is wrong.",
    parameters: Type.Object({
      taskId: Type.String({ description: "Task to reparent" }),
      newParent: Type.Optional(Type.String({ description: "New parent task ID, or omit to make it a root" })),
      reason: Type.String({ description: "Why this restructuring is needed" }),
    }),
    async execute(_toolCallId: string, params: { taskId: string; newParent?: string; reason: string }) {
      const task = graph.readTask(params.taskId);
      if (!task) return textResult(`Task ${params.taskId} not found.`);
      if (params.newParent === params.taskId) {
        return textResult(`Cannot reparent ${params.taskId} under itself.`);
      }
      if (params.newParent) {
        const newParent = graph.readTask(params.newParent);
        if (!newParent) return textResult(`New parent ${params.newParent} not found.`);
        const descendants = collectDescendants(params.taskId);
        if (descendants.has(params.newParent)) {
          return textResult(`Cannot reparent ${params.taskId} under ${params.newParent}: would create a cycle.`);
        }
      }

      const now = new Date().toISOString();

      // Remove from old parent
      if (task.parent) {
        const oldParent = graph.readTask(task.parent);
        if (oldParent) {
          oldParent.children = oldParent.children.filter(c => c !== params.taskId);
          oldParent.updatedAt = now;
          graph.writeTask(oldParent);
        }
      }

      // Add to new parent
      task.parent = params.newParent;
      task.updatedAt = now;
      if (params.newParent) {
        const newParent = graph.readTask(params.newParent);
        if (!newParent) return textResult(`New parent ${params.newParent} not found.`);
        if (!newParent.children.includes(params.taskId)) newParent.children.push(params.taskId);
        newParent.updatedAt = now;
        graph.writeTask(newParent);
      }

      graph.writeTask(task);
      return textResult(`Reparented ${params.taskId} → ${params.newParent ?? "(root)"}. Reason: ${params.reason}`);
    },
  };

  const resolveBlocker = {
    name: "graph_resolve_blocker",
    label: "Resolve Blocker",
    description: "Mark a blocker as resolved. If all blockers on a task are resolved, the task is automatically unblocked.",
    parameters: Type.Object({
      blockerId: Type.String({ description: "Blocker ID" }),
      resolution: Type.String({ description: "How this was resolved — cite evidence" }),
    }),
    async execute(_toolCallId: string, params: { blockerId: string; resolution: string }) {
      const blocker = graph.readBlocker(params.blockerId);
      if (!blocker) return textResult(`Blocker ${params.blockerId} not found.`);

      blocker.status = "resolved";
      graph.writeBlocker(blocker);

      // Auto-unblock tasks if all their blockers are resolved
      const now = new Date().toISOString();
      for (const taskId of blocker.affectedTasks) {
        const task = graph.readTask(taskId);
        if (!task || task.status !== "blocked") continue;

        const allResolved = task.blockers.every(bId => {
          const b = graph.readBlocker(bId);
          return !b || b.status !== "open";
        });

        if (allResolved) {
          task.status = "queued";
          task.updatedAt = now;
          graph.writeTask(task);
        }
      }

      return textResult(`Resolved ${params.blockerId}. Resolution: ${params.resolution}`);
    },
  };

  const deleteBlocker = {
    name: "graph_delete_blocker",
    label: "Delete Blocker",
    description: "Permanently delete a blocker from disk. Use for duplicates or noise.",
    parameters: Type.Object({
      blockerId: Type.String({ description: "Blocker ID to delete" }),
      reason: Type.String({ description: "Why this blocker is being deleted" }),
    }),
    async execute(_toolCallId: string, params: { blockerId: string; reason: string }) {
      const blocker = graph.readBlocker(params.blockerId);
      if (!blocker) return textResult(`Blocker ${params.blockerId} not found.`);

      const now = new Date().toISOString();
      for (const taskId of blocker.affectedTasks) {
        const task = graph.readTask(taskId);
        if (!task) continue;

        task.blockedBy = task.blockedBy.filter(id => id !== params.blockerId);
        task.blockers = task.blockers.filter(id => id !== params.blockerId);

        if (task.status === "blocked") {
          const hasOpenBlockers = task.blockers.some(id => {
            const b = graph.readBlocker(id);
            return b?.status === "open";
          });
          if (!hasOpenBlockers) task.status = "queued";
        }

        task.updatedAt = now;
        graph.writeTask(task);
      }

      graph.deleteBlocker(params.blockerId);
      return textResult(`Deleted blocker ${params.blockerId}. Reason: ${params.reason}`);
    },
  };

  const queryGraph = {
    name: "graph_query",
    label: "Query Graph",
    description: "Get a full state dump of the task graph: status breakdown, open blockers, blocker clusters, pending reviews, cycle detection.",
    parameters: Type.Object({}),
    async execute() {
      const tasks = graph.listTasks();
      const blockers = graph.listBlockers();
      const openBlockers = graph.openBlockers();
      const openTasks = graph.openTasks();
      const clusters = graph.blockerClusters();
      const multiClusters = [...clusters.entries()].filter(([, v]) => v.length >= 2);
      const cycle = graph.detectCycle();
      const pendingReview = tasks.filter(t => t.status === "done_pending_review");
      const roots = graph.roots();

      // Status breakdown
      const statusCounts = new Map<string, number>();
      for (const t of tasks) {
        statusCounts.set(t.status, (statusCounts.get(t.status) ?? 0) + 1);
      }

      const lines = [
        `# Task Graph State`,
        ``,
        `Tasks: ${tasks.length} total, ${openTasks.length} open`,
        `Blockers: ${blockers.length} total, ${openBlockers.length} open`,
        `Pending review: ${pendingReview.length}`,
        `Root tasks: ${roots.length}`,
        cycle ? `\n⚠ CYCLE DETECTED: ${cycle.join(" → ")}` : "",
        ``,
        `## Status Breakdown`,
        ...[...statusCounts.entries()].map(([s, n]) => `- ${s}: ${n}`),
        ``,
        `## Open Blockers`,
        ...(openBlockers.length > 0
          ? openBlockers.map(b => `- ${b.id} [sev:${b.severity}] ${b.summary} (fp: ${b.fingerprint}, by: ${b.creator})`)
          : ["(none)"]),
        ``,
        `## Blocker Clusters (repeated root causes)`,
        ...(multiClusters.length > 0
          ? multiClusters.map(([key, bs]) => `- "${key}": ${bs.length} instances`)
          : ["(none)"]),
        ``,
        `## Pending Review`,
        ...(pendingReview.length > 0
          ? pendingReview.map(t => `- ${t.id} [${t.evidenceClass ?? "?"}] ${t.scope} by ${t.creator}`)
          : ["(none)"]),
        ``,
        `## All Tasks`,
        ...tasks.map(t => {
          const indent = t.parent ? "  " : "";
          return `${indent}- ${t.id} [${t.status}] ${t.scope} (creator: ${t.creator}, children: ${t.children.length}, blockers: ${t.blockers.length})`;
        }),
      ];

      return textResult(lines.filter(l => l !== undefined).join("\n"));
    },
  };

  const listTasks = {
    name: "graph_list_tasks",
    label: "List Tasks",
    description: "List all tasks in the graph, optionally filtered by status.",
    parameters: Type.Object({
      status: Type.Optional(Type.String({ description: "Filter by status" })),
    }),
    async execute(_toolCallId: string, params: { status?: string }) {
      const tasks = params.status ? graph.tasksByStatus(params.status) : graph.listTasks();
      if (tasks.length === 0) return textResult("No tasks found.");
      const lines = tasks.map(t =>
        `${t.id} [${t.status}] ${t.scope} (creator: ${t.creator}, children: ${t.children.length}, blockers: ${t.blockers.length})`,
      );
      return textResult(lines.join("\n"));
    },
  };

  const listBlockers = {
    name: "graph_list_blockers",
    label: "List Blockers",
    description: "List all blockers, optionally only open ones.",
    parameters: Type.Object({
      openOnly: Type.Optional(Type.Boolean({ description: "Only show open blockers" })),
    }),
    async execute(_toolCallId: string, params: { openOnly?: boolean }) {
      const blockers = params.openOnly ? graph.openBlockers() : graph.listBlockers();
      if (blockers.length === 0) return textResult("No blockers found.");
      const lines = blockers.map(b =>
        `${b.id} [sev:${b.severity}] [${b.status}] ${b.summary} (fp: ${b.fingerprint}, by: ${b.creator})`,
      );
      return textResult(lines.join("\n"));
    },
  };

  const emitHandoff = {
    name: "graph_emit_handoff",
    label: "Emit Role-Boundary Handoff",
    description: "Write a structured handoff artifact when reviewer authority blocks requested work (e.g. task/blocker creation owned by coder role).",
    parameters: Type.Object({
      attemptedAction: Type.String({ description: "Action that was requested but blocked in this reviewer session." }),
      requiredRole: Type.String({ description: "Role required to complete the blocked action, usually 'coder'." }),
      reason: Type.String({ description: "Why this action is blocked in current role." }),
      payload: Type.String({ description: "Minimal handoff payload (exact records/changes needed)." }),
      evidence: Type.Optional(Type.Array(Type.String({ description: "Supporting evidence references (file:line, tool errors, etc.)." }))),
    }),
    async execute(
      _toolCallId: string,
      params: { attemptedAction: string; requiredRole: string; reason: string; payload: string; evidence?: string[] },
    ) {
      const now = new Date();
      const iso = now.toISOString();
      const stamp = iso.replace(/[-:]/g, "").replace(/\..+/, "");
      const entropy = Math.random().toString(36).slice(2, 8);
      const id = `H-${stamp}-${entropy}`;
      const path = join(handoffsDir, `${id}.md`);
      const evidence = params.evidence ?? [];

      const content = `---
id: ${id}
status: open
from_role: reviewer
to_role: ${params.requiredRole}
creator: ${reviewerId}
created_at: ${iso}
attempted_action: ${params.attemptedAction}
denied_operation: role-boundary
---

## Why blocked
${params.reason}

## Minimal handoff payload
${params.payload}

## Evidence
${evidence.length > 0 ? evidence.map((e) => `- ${e}`).join("\n") : "- (none provided)"}
`;

      writeFileSync(path, content);
      return textResult(`ROLE-BOUNDARY BLOCKED handoff recorded: ${id}\nPath: ${path}\nNext: hand this artifact to a ${params.requiredRole} session.`);
    },
  };

  return [closeTask, deleteTask, reparentTask, resolveBlocker, deleteBlocker, queryGraph, listTasks, listBlockers, emitHandoff];
}
