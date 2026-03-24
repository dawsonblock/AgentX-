/**
 * Context Packer Implementation
 * 
 * Ranks and packs context items within token budget.
 * Loads real file contents from the filesystem.
 */

import * as fs from 'fs';
import * as path from 'path';
import {
  ContextPackerInput,
  ContextPack,
  ContextItem,
  CodeSnippet
} from './contracts';

// Maximum file size to load (100KB)
const MAX_FILE_SIZE = 100 * 1024;

// Maximum tokens per file
const MAX_TOKENS_PER_FILE = 4000;

// Simple token estimation (very rough)
function estimateTokens(text: string): number {
  // Rough estimate: ~4 characters per token for code
  return Math.ceil(text.length / 4);
}

/**
 * Read file content from filesystem.
 */
function readFileContent(filePath: string): string | null {
  try {
    // Check if file exists and is within size limit
    const stats = fs.statSync(filePath);
    if (stats.size > MAX_FILE_SIZE) {
      return `// File: ${path.basename(filePath)}\n// (File too large: ${stats.size} bytes)`;
    }
    
    return fs.readFileSync(filePath, 'utf-8');
  } catch (error) {
    return null;
  }
}

/**
 * Read multiple files and return their contents.
 */
function readFiles(worktreePath: string, filePaths: string[]): Map<string, string> {
  const contents = new Map<string, string>();
  
  for (const filePath of filePaths) {
    const fullPath = path.join(worktreePath, filePath);
    const content = readFileContent(fullPath);
    if (content !== null) {
      contents.set(filePath, content);
    }
  }
  
  return contents;
}

/**
 * Truncate content to fit within token budget.
 */
function truncateContent(content: string, maxTokens: number): string {
  const estimatedTokens = estimateTokens(content);
  
  if (estimatedTokens <= maxTokens) {
    return content;
  }
  
  // Truncate to approximately maxTokens
  const maxChars = maxTokens * 4;
  const truncated = content.substring(0, maxChars);
  
  return truncated + '\n\n// ... (truncated)';
}

// Fallback ranker scoring
function scoreItem(
  item: ContextItem,
  input: ContextPackerInput
): number {
  let score = item.relevanceScore;
  
  // Boost for test file overlap with failing tests
  if (input.failingTestLogs && item.path) {
    const testNameMatch = input.failingTestLogs
      .toLowerCase()
      .includes(item.path.toLowerCase());
    if (testNameMatch) {
      score += 0.5;
    }
  }
  
  // Boost for recent diffs
  if (item.type === 'diff') {
    score += 0.3;
  }
  
  // Boost for files that match task keywords
  if (input.taskDescription && item.path) {
    const taskKeywords = input.taskDescription
      .toLowerCase()
      .split(/\s+/)
      .filter(w => w.length > 3);
    
    const pathLower = item.path.toLowerCase();
    for (const keyword of taskKeywords) {
      if (pathLower.includes(keyword)) {
        score += 0.2;
      }
    }
  }
  
  return score;
}

/**
 * Build context pack from input with real file contents.
 */
export async function buildContext(
  input: ContextPackerInput,
  budgetTokens: number = 24000
): Promise<ContextPack> {
  const items: ContextItem[] = [];
  
  // Load real file contents from worktree
  if (input.worktreePath && input.candidateFiles.length > 0) {
    const fileContents = readFiles(input.worktreePath, input.candidateFiles);
    
    for (const [filePath, content] of fileContents) {
      // Truncate large files
      const truncatedContent = truncateContent(content, MAX_TOKENS_PER_FILE);
      
      items.push({
        type: 'file',
        path: filePath,
        content: `// File: ${filePath}\n${truncatedContent}`,
        relevanceScore: 0.5,
        rationale: `Candidate file from structural analysis (${estimateTokens(truncatedContent)} tokens)`
      });
    }
    
    // Add placeholder for files that couldn't be loaded
    for (const filePath of input.candidateFiles) {
      if (!fileContents.has(filePath)) {
        items.push({
          type: 'file',
          path: filePath,
          content: `// File: ${filePath}\n// (Could not load file content)`,
          relevanceScore: 0.3,
          rationale: `Candidate file (content unavailable)`
        });
      }
    }
  } else {
    // Fallback: placeholder content if no worktree
    for (const filePath of input.candidateFiles) {
      items.push({
        type: 'file',
        path: filePath,
        content: `// File: ${filePath}\n// (Content would be loaded from ${input.worktreePath || 'worktree'})`,
        relevanceScore: 0.5,
        rationale: `Candidate file from structural analysis`
      });
    }
  }
  
  // Add selected snippets (already have content)
  for (const snippet of (input.selectedSnippets || [])) {
    items.push({
      type: 'snippet',
      path: snippet.path,
      content: snippet.content,
      relevanceScore: snippet.relevanceScore,
      rationale: `Selected snippet from ${snippet.path}`
    });
  }
  
  // Add docs
  for (const doc of (input.repoDocs || [])) {
    items.push({
      type: 'doc',
      content: doc,
      relevanceScore: 0.4,
      rationale: 'Repository documentation'
    });
  }
  
  // Add diffs
  for (const diff of (input.recentDiffs || [])) {
    items.push({
      type: 'diff',
      content: diff,
      relevanceScore: 0.3,
      rationale: 'Recent code changes'
    });
  }
  
  // Score all items
  const scoredItems = items.map(item => ({
    ...item,
    score: scoreItem(item, input)
  }));
  
  // Sort by score descending
  scoredItems.sort((a, b) => b.score - a.score);
  
  // Pack items within budget
  const selectedItems: ContextItem[] = [];
  let usedTokens = 0;
  const rationale: string[] = [];
  
  // Reserve tokens for task description
  const taskTokens = estimateTokens(input.taskDescription);
  const availableTokens = budgetTokens - taskTokens - 1000; // Buffer
  
  for (const item of scoredItems) {
    const itemTokens = estimateTokens(item.content);
    
    if (usedTokens + itemTokens <= availableTokens) {
      selectedItems.push(item);
      usedTokens += itemTokens;
      rationale.push(`${item.type}: ${item.path || 'doc'} - ${item.rationale}`);
    }
  }
  
  // Build final pack
  const finalPack = [
    `Task: ${input.taskDescription}`,
    `\nContext:\n`,
    ...selectedItems.map(item => `
--- ${item.type}: ${item.path || 'doc'} ---
${item.content}
`)
  ].join('\n');
  
  return {
    selectedItems,
    rationale,
    budgetTokens,
    usedTokens: usedTokens + taskTokens,
    finalPack
  };
}

/**
 * Build context with file discovery.
 * Discovers files from the worktree if candidateFiles not provided.
 */
export async function buildContextWithDiscovery(
  worktreePath: string,
  taskDescription: string,
  budgetTokens: number = 24000
): Promise<ContextPack> {
  // Discover relevant files
  const candidateFiles: string[] = [];
  
  try {
    // Walk the directory and find source files
    function walkDir(dir: string, basePath: string = '') {
      const entries = fs.readdirSync(path.join(worktreePath, dir), { withFileTypes: true });
      
      for (const entry of entries) {
        const relativePath = path.join(basePath, entry.name);
        
        // Skip common non-source directories
        if (entry.isDirectory()) {
          if (['node_modules', '.git', '__pycache__', '.venv', 'venv', 'dist', 'build'].includes(entry.name)) {
            continue;
          }
          walkDir(relativePath, relativePath);
        } else if (entry.isFile()) {
          // Include common source file extensions
          const ext = path.extname(entry.name).toLowerCase();
          if (['.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs', '.cpp', '.c', '.h'].includes(ext)) {
            candidateFiles.push(relativePath);
          }
        }
      }
    }
    
    walkDir('');
    
    // Limit to first 50 files to avoid overwhelming
    candidateFiles.splice(50);
    
  } catch (error) {
    console.error('Failed to discover files:', error);
  }
  
  const input: ContextPackerInput = {
    taskDescription,
    worktreePath,
    candidateFiles,
    selectedSnippets: [],
    repoDocs: [],
    recentDiffs: []
  };
  
  return buildContext(input, budgetTokens);
}

// Export contracts
export * from './contracts';
