/**
 * Coder tools — additive-only authority over the task graph.
 *
 * Coders can create tasks, report blockers, update their own task status
 * (non-terminal only), and list/read graph state. They cannot delete,
 * close, resolve, or restructure anything.
 */

import { Type } from "@sinclair/typebox";
import { GraphStore } from "./store.js";
import { CODER_ALLOWED_STATUSES } from "./types.js";
import type { TaskNode, BlockerNode } from "./types.js";

function textResult(text: string) {
  return { content: [{ type: "text" as const, text }], details: {} };
}

export function createCoderTools(graphDir: string, agentId: string) {
  const graph = new GraphStore(graphDir);

  const createTask = {
    name: "graph_create_task",
    label: "Create Task",
    description: "Create a new task in the task graph. You can optionally set a parent to create a subtask. The task starts in 'queued' status.",
    parameters: Type.Object({
      scope: Type.String({ description: "What this task is about" }),
      parent: Type.Optional(Type.String({ description: "Parent task ID (e.g. T-1234) to create a subtask" })),
    }),
    async execute(_toolCallId: string, params: { scope: string; parent?: string }) {
      if (params.parent && !graph.readTask(params.parent)) {
        return textResult(`Parent task ${params.parent} not found.`);
      }

      const id = `T-${Date.now()}`;
      const now = new Date().toISOString();
      const task: TaskNode = {
        id,
        status: "queued",
        scope: params.scope,
        creator: agentId,
        createdAt: now,
        updatedAt: now,
        parent: params.parent,
        children: [],
        blockedBy: [],
        blockers: [],
      };
      graph.writeTask(task);

      if (params.parent) {
        const parent = graph.readTask(params.parent);
        if (parent) {
          if (!parent.children.includes(id)) parent.children.push(id);
          parent.updatedAt = now;
          graph.writeTask(parent);
        }
      }

      return textResult(`Created task ${id}: ${params.scope}`);
    },
  };

  const reportBlocker = {
    name: "graph_report_blocker",
    label: "Report Blocker",
    description: "Report a blocker. Include a deterministic fingerprint for the root cause so duplicate blockers can be clustered. Affected tasks will be automatically marked as blocked.",
    parameters: Type.Object({
      summary: Type.String({ description: "One-line summary" }),
      fingerprint: Type.String({ description: "Deterministic key for root cause (e.g. 'missing-udp-transport', 'vt-oracle-mismatch')" }),
      severity: Type.Number({ description: "1=low, 2=medium, 3=critical" }),
      whatWasAttempted: Type.String({ description: "What you were trying to do" }),
      whatFailed: Type.String({ description: "What went wrong" }),
      evidence: Type.Array(Type.String(), { description: "File:line references or error messages" }),
      affectedTasks: Type.Array(Type.String(), { description: "Task IDs affected by this blocker" }),
      suggestedNextAction: Type.String({ description: "What should happen next to resolve this" }),
      retryable: Type.Boolean({ description: "Whether a retry might succeed" }),
    }),
    async execute(_toolCallId: string, params: {
      summary: string; fingerprint: string; severity: number;
      whatWasAttempted: string; whatFailed: string; evidence: string[];
      affectedTasks: string[]; suggestedNextAction: string; retryable: boolean;
    }) {
      const id = `B-${Date.now()}`;
      const blocker: BlockerNode = {
        id,
        severity: Math.min(3, Math.max(1, params.severity)) as 1 | 2 | 3,
        status: "open",
        creator: agentId,
        createdAt: new Date().toISOString(),
        fingerprint: params.fingerprint,
        summary: params.summary,
        whatWasAttempted: params.whatWasAttempted,
        whatFailed: params.whatFailed,
        evidence: params.evidence,
        affectedTasks: params.affectedTasks,
        suggestedNextAction: params.suggestedNextAction,
        retryable: params.retryable,
      };
      graph.writeBlocker(blocker);

      // Auto-block affected tasks
      const now = new Date().toISOString();
      for (const taskId of params.affectedTasks) {
        const task = graph.readTask(taskId);
        if (task) {
          if (!task.blockedBy.includes(id)) task.blockedBy.push(id);
          if (!task.blockers.includes(id)) task.blockers.push(id);
          task.status = "blocked";
          task.updatedAt = now;
          graph.writeTask(task);
        }
      }

      return textResult(`Reported blocker ${id}: ${params.summary} (fingerprint: ${params.fingerprint})`);
    },
  };

  const updateTaskStatus = {
    name: "graph_update_task_status",
    label: "Update Task Status",
    description: `Update a task's status. Coders can only set: ${CODER_ALLOWED_STATUSES.join(", ")}. Terminal states (accepted, closed, rejected) require reviewer authority.`,
    parameters: Type.Object({
      taskId: Type.String({ description: "Task ID" }),
      status: Type.String({ description: `New status: ${CODER_ALLOWED_STATUSES.join(" | ")}` }),
      evidenceClass: Type.Optional(Type.String({ description: "Evidence class: unit | simulation | smoke | integration | behavioral | production" })),
      evidence: Type.Optional(Type.Array(Type.String(), { description: "Evidence references" })),
      knownGaps: Type.Optional(Type.Array(Type.String(), { description: "Known gaps or missing coverage" })),
    }),
    async execute(_toolCallId: string, params: {
      taskId: string; status: string;
      evidenceClass?: string; evidence?: string[]; knownGaps?: string[];
    }) {
      if (!CODER_ALLOWED_STATUSES.includes(params.status as any)) {
        return textResult(`Denied: coders cannot set status to "${params.status}". Terminal states require reviewer authority.`);
      }

      const task = graph.readTask(params.taskId);
      if (!task) return textResult(`Task ${params.taskId} not found.`);

      task.status = params.status as any;
      task.updatedAt = new Date().toISOString();
      if (params.evidenceClass) task.evidenceClass = params.evidenceClass as any;
      if (params.evidence) task.evidence = params.evidence;
      if (params.knownGaps) task.knownGaps = params.knownGaps;
      graph.writeTask(task);

      return textResult(`Updated ${params.taskId} → ${params.status}`);
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

  return [createTask, reportBlocker, updateTaskStatus, listTasks, listBlockers];
}
