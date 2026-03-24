/**
 * Orchestrator Adapter Contracts
 * 
 * This module defines the narrow interface between the runtime
 * and the agent orchestrator donor.
 */

export interface WorktreeAllocation {
  worktreeId: string;
  runId: string;
  repoId: string;
  path: string;
  branchName: string;
  baseRef: string;
  status: 'active' | 'released' | 'failed';
  createdAt: Date;
}

export interface SessionState {
  sessionId: string;
  runId: string;
  status: 'starting' | 'running' | 'paused' | 'stopped' | 'failed';
  worktreePath: string;
  startedAt?: Date;
  stoppedAt?: Date;
}

export interface AllocateWorktreeRequest {
  runId: string;
  repoId: string;
  baseRef: string;
  repoUrl?: string;
}

export interface StartSessionRequest {
  runId: string;
  workerProfile: string;
  worktreePath: string;
  contextPack?: unknown;
}

export interface OrchestratorAdapter {
  allocateWorktree(req: AllocateWorktreeRequest): Promise<WorktreeAllocation>;
  releaseWorktree(runId: string): Promise<void>;
  startWorkerSession(req: StartSessionRequest): Promise<SessionState>;
  pauseWorkerSession(runId: string): Promise<SessionState>;
  resumeWorkerSession(runId: string): Promise<SessionState>;
  cancelWorkerSession(runId: string): Promise<SessionState>;
  getSessionState(runId: string): Promise<SessionState | null>;
}
