/**
 * Worker session management for orchestrator adapter.
 */

import { SessionState, StartSessionRequest } from './contracts';

// In-memory session store (replace with persistent storage in production)
const sessions = new Map<string, SessionState>();

/**
 * Start a worker session.
 */
export async function startWorkerSession(
  req: StartSessionRequest
): Promise<SessionState> {
  const sessionId = `session-${req.runId}`;
  
  const state: SessionState = {
    sessionId,
    runId: req.runId,
    status: 'starting',
    worktreePath: req.worktreePath,
    startedAt: new Date()
  };
  
  // Store session
  sessions.set(req.runId, state);
  
  // In real implementation, this would:
  // 1. Spawn the worker process
  // 2. Connect to GSD wrapper
  // 3. Initialize with context pack
  
  // Mark as running
  state.status = 'running';
  
  return state;
}

/**
 * Pause a worker session.
 */
export async function pauseWorkerSession(runId: string): Promise<SessionState> {
  const state = sessions.get(runId);
  
  if (!state) {
    throw new Error(`No session found for run ${runId}`);
  }
  
  if (state.status !== 'running') {
    throw new Error(`Cannot pause session in state ${state.status}`);
  }
  
  // In real implementation, this would signal the worker to pause
  state.status = 'paused';
  
  return state;
}

/**
 * Resume a worker session.
 */
export async function resumeWorkerSession(runId: string): Promise<SessionState> {
  const state = sessions.get(runId);
  
  if (!state) {
    throw new Error(`No session found for run ${runId}`);
  }
  
  if (state.status !== 'paused') {
    throw new Error(`Cannot resume session in state ${state.status}`);
  }
  
  // In real implementation, this would signal the worker to resume
  state.status = 'running';
  
  return state;
}

/**
 * Cancel a worker session.
 */
export async function cancelWorkerSession(runId: string): Promise<SessionState> {
  const state = sessions.get(runId);
  
  if (!state) {
    throw new Error(`No session found for run ${runId}`);
  }
  
  // In real implementation, this would:
  // 1. Signal the worker to stop
  // 2. Wait for graceful shutdown
  // 3. Force kill if needed
  
  state.status = 'stopped';
  state.stoppedAt = new Date();
  
  return state;
}

/**
 * Get session state.
 */
export async function getSessionState(
  runId: string
): Promise<SessionState | null> {
  return sessions.get(runId) || null;
}

/**
 * List all active sessions.
 */
export async function listActiveSessions(): Promise<SessionState[]> {
  return Array.from(sessions.values()).filter(
    s => s.status === 'running' || s.status === 'paused'
  );
}
