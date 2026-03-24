export type TaskStatus =
  | "queued"
  | "in_progress"
  | "blocked"
  | "done_pending_review"
  | "accepted"
  | "closed"
  | "rejected"
  | "deferred";

export const CODER_ALLOWED_STATUSES: TaskStatus[] = [
  "queued", "in_progress", "blocked", "deferred", "done_pending_review",
];

export const TERMINAL_STATUSES: TaskStatus[] = [
  "accepted", "closed", "rejected",
];

export type BlockerSeverity = 1 | 2 | 3;

export type EvidenceClass =
  | "unit"
  | "simulation"
  | "smoke"
  | "integration"
  | "behavioral"
  | "production";

export interface TaskNode {
  id: string;
  status: TaskStatus;
  scope: string;
  creator: string;
  createdAt: string;
  updatedAt: string;
  parent?: string;
  children: string[];
  blockedBy: string[];
  blockers: string[];
  evidenceClass?: EvidenceClass;
  evidence?: string[];
  knownGaps?: string[];
  commitRefs?: string[];
}

export interface BlockerNode {
  id: string;
  severity: BlockerSeverity;
  status: "open" | "triaged" | "resolved" | "wont_fix";
  summary: string;
  creator: string;
  createdAt: string;
  fingerprint: string;
  whatWasAttempted: string;
  whatFailed: string;
  evidence: string[];
  affectedTasks: string[];
  suggestedNextAction: string;
  retryable: boolean;
}
