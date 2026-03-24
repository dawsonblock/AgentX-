/**
 * Context Packer Implementation
 * 
 * Ranks and packs context items within token budget.
 */

import {
  ContextPackerInput,
  ContextPack,
  ContextItem,
  CodeSnippet
} from './contracts';

// Simple token estimation (very rough)
function estimateTokens(text: string): number {
  // Rough estimate: ~4 characters per token for code
  return Math.ceil(text.length / 4);
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
  
  return score;
}

/**
 * Build context pack from input.
 */
export async function buildContext(
  input: ContextPackerInput,
  budgetTokens: number = 24000
): Promise<ContextPack> {
  const items: ContextItem[] = [];
  
  // Add candidate files as snippets
  for (const path of input.candidateFiles) {
    items.push({
      type: 'file',
      path,
      content: `// File: ${path}\n// (Content would be loaded here)`,
      relevanceScore: 0.5,
      rationale: `Candidate file from structural analysis`
    });
  }
  
  // Add selected snippets
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

// Export contracts
export * from './contracts';
