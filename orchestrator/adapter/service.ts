/**
 * Orchestrator Adapter Service
 * 
 * Main entry point for orchestrator operations.
 * Implements the OrchestratorAdapter interface.
 */

import {
  OrchestratorAdapter,
  WorktreeAllocation,
  SessionState,
  AllocateWorktreeRequest,
  StartSessionRequest
} from './contracts';
import {
  allocateWorktree,
  releaseWorktree,
  cleanupStaleWorktrees
} from './worktrees';
import {
  startWorkerSession,
  pauseWorkerSession,
  resumeWorkerSession,
  cancelWorkerSession,
  getSessionState,
  listActiveSessions
} from './sessions';

// Export all contracts
export * from './contracts';
export { cleanupStaleWorktrees, listActiveSessions };

/**
 * Create an orchestrator adapter instance.
 */
export function createOrchestratorAdapter(): OrchestratorAdapter {
  return {
    allocateWorktree,
    releaseWorktree,
    startWorkerSession,
    pauseWorkerSession,
    resumeWorkerSession,
    cancelWorkerSession,
    getSessionState
  };
}

// Default export
export default createOrchestratorAdapter;
