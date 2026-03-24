/**
 * Worktree management for orchestrator adapter.
 * 
 * Handles git worktree allocation, branch management, and cleanup.
 */

import { execSync, spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import { WorktreeAllocation, AllocateWorktreeRequest } from './contracts';

const WORKTREE_ROOT = process.env.WORKTREE_ROOT || '/var/lib/product/worktrees';
const REPO_ROOT = process.env.REPO_ROOT || '/repos';

// Ensure worktree root exists
function ensureWorktreeRoot(): void {
  if (!fs.existsSync(WORKTREE_ROOT)) {
    fs.mkdirSync(WORKTREE_ROOT, { recursive: true });
  }
}

/**
 * Generate branch name for a run.
 */
function generateBranchName(runId: string, taskType: string): string {
  const shortRunId = runId.replace(/-/g, '').substring(0, 8);
  const shortTask = taskType.replace(/[^a-zA-Z0-9]/g, '-').substring(0, 30);
  return `product/run-${shortRunId}-${shortTask}`;
}

/**
 * Generate worktree path for a run.
 */
function generateWorktreePath(runId: string): string {
  return path.join(WORKTREE_ROOT, runId);
}

/**
 * Get repository path from repo ID.
 */
function getRepoPath(repoId: string): string {
  // Check if it's an absolute path
  if (fs.existsSync(repoId)) {
    return repoId;
  }
  
  // Check in repo root
  const repoPath = path.join(REPO_ROOT, repoId);
  if (fs.existsSync(repoPath)) {
    return repoPath;
  }
  
  // Check if it's a URL
  if (repoId.startsWith('http://') || repoId.startsWith('https://') || repoId.startsWith('git@')) {
    return repoId;
  }
  
  throw new Error(`Repository not found: ${repoId}`);
}

/**
 * Get current git ref.
 */
function getCurrentRef(repoPath: string): string {
  try {
    const result = execSync('git rev-parse HEAD', {
      cwd: repoPath,
      encoding: 'utf-8',
      timeout: 10000
    });
    return result.trim();
  } catch (e) {
    throw new Error(`Failed to get current ref: ${e}`);
  }
}

/**
 * Clone a repository.
 */
function cloneRepo(repoUrl: string, targetPath: string, depth: number = 1): void {
  const cmd = `git clone ${depth > 0 ? `--depth=${depth}` : ''} "${repoUrl}" "${targetPath}"`;
  
  try {
    execSync(cmd, {
      timeout: 120000,
      stdio: 'pipe'
    });
  } catch (e) {
    throw new Error(`Clone failed: ${e}`);
  }
}

/**
 * Create and checkout a new branch.
 */
function createBranch(worktreePath: string, branchName: string, baseRef: string): void {
  try {
    // Create branch from base ref
    execSync(`git checkout -b ${branchName} ${baseRef}`, {
      cwd: worktreePath,
      timeout: 10000,
      stdio: 'pipe'
    });
  } catch (e) {
    throw new Error(`Failed to create branch: ${e}`);
  }
}

/**
 * Clean up a worktree directory.
 */
function cleanupWorktree(worktreePath: string): void {
  if (!fs.existsSync(worktreePath)) {
    return;
  }
  
  // Use rm -rf for thorough cleanup
  try {
    fs.rmSync(worktreePath, { recursive: true, force: true });
  } catch (e) {
    console.warn(`Failed to clean up worktree ${worktreePath}: ${e}`);
  }
}

/**
 * Allocate a worktree for a run.
 */
export async function allocateWorktree(
  req: AllocateWorktreeRequest
): Promise<WorktreeAllocation> {
  ensureWorktreeRoot();
  
  const worktreePath = generateWorktreePath(req.runId);
  const branchName = generateBranchName(req.runId, req.repoId);
  
  // Clean up any existing worktree at this path
  cleanupWorktree(worktreePath);
  
  // Determine repository source
  let repoPath: string;
  let isRemote = false;
  
  try {
    repoPath = getRepoPath(req.repoId);
  } catch (e) {
    // Assume it's a remote URL
    repoPath = req.repoId;
    isRemote = true;
  }
  
  // Determine base ref
  let baseRef = req.baseRef;
  
  try {
    if (isRemote) {
      // Clone the repository
      cloneRepo(repoPath, worktreePath);
      
      // Get default branch ref if not specified
      if (!baseRef) {
        baseRef = getCurrentRef(worktreePath);
      }
    } else {
      // Local repository - clone to worktree
      cloneRepo(repoPath, worktreePath);
      
      // Get current ref if not specified
      if (!baseRef) {
        baseRef = getCurrentRef(worktreePath);
      }
    }
    
    // Create and checkout branch
    createBranch(worktreePath, branchName, baseRef);
    
    return {
      worktreeId: req.runId,
      runId: req.runId,
      repoId: req.repoId,
      path: worktreePath,
      branchName,
      baseRef,
      status: 'active',
      createdAt: new Date()
    };
  } catch (e) {
    // Cleanup on failure
    cleanupWorktree(worktreePath);
    throw e;
  }
}

/**
 * Release a worktree for a run.
 */
export async function releaseWorktree(runId: string): Promise<void> {
  const worktreePath = generateWorktreePath(runId);
  cleanupWorktree(worktreePath);
}

/**
 * Get worktree info.
 */
export async function getWorktreeInfo(runId: string): Promise<Partial<WorktreeAllocation> | null> {
  const worktreePath = generateWorktreePath(runId);
  
  if (!fs.existsSync(worktreePath)) {
    return null;
  }
  
  try {
    // Get current branch
    const branchResult = execSync('git branch --show-current', {
      cwd: worktreePath,
      encoding: 'utf-8',
      timeout: 5000
    });
    
    // Get current ref
    const refResult = execSync('git rev-parse HEAD', {
      cwd: worktreePath,
      encoding: 'utf-8',
      timeout: 5000
    });
    
    return {
      worktreeId: runId,
      runId,
      path: worktreePath,
      branchName: branchResult.trim(),
      baseRef: refResult.trim(),
      status: 'active'
    };
  } catch (e) {
    return null;
  }
}

/**
 * Clean up stale worktrees.
 */
export async function cleanupStaleWorktrees(maxAgeHours: number = 24): Promise<number> {
  if (!fs.existsSync(WORKTREE_ROOT)) {
    return 0;
  }
  
  const entries = fs.readdirSync(WORKTREE_ROOT);
  const now = Date.now();
  let cleaned = 0;
  
  for (const entry of entries) {
    const entryPath = path.join(WORKTREE_ROOT, entry);
    
    try {
      const stats = fs.statSync(entryPath);
      const ageHours = (now - stats.mtime.getTime()) / (1000 * 60 * 60);
      
      if (ageHours > maxAgeHours) {
        cleanupWorktree(entryPath);
        cleaned++;
        console.log(`Cleaned up stale worktree: ${entry}`);
      }
    } catch (e) {
      console.warn(`Failed to check worktree ${entry}: ${e}`);
    }
  }
  
  return cleaned;
}

/**
 * Sync worktree with remote (if applicable).
 */
export async function syncWorktree(runId: string): Promise<void> {
  const worktreePath = generateWorktreePath(runId);
  
  if (!fs.existsSync(worktreePath)) {
    throw new Error(`Worktree not found for run ${runId}`);
  }
  
  try {
    // Fetch latest changes
    execSync('git fetch origin', {
      cwd: worktreePath,
      timeout: 30000,
      stdio: 'pipe'
    });
  } catch (e) {
    console.warn(`Failed to sync worktree ${runId}: ${e}`);
  }
}
