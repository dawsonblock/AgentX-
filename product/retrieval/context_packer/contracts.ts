/**
 * Context Packer Contracts
 * 
 * Defines the interface for bounded context packing.
 */

export interface ContextPackerInput {
  taskDescription: string;
  failingTestLogs?: string;
  candidateFiles: string[];
  repoDocs?: string[];
  recentDiffs?: string[];
  selectedSnippets?: CodeSnippet[];
}

export interface CodeSnippet {
  path: string;
  content: string;
  startLine: number;
  endLine: number;
  relevanceScore: number;
}

export interface ContextItem {
  type: 'file' | 'snippet' | 'doc' | 'diff';
  path?: string;
  content: string;
  relevanceScore: number;
  rationale: string;
}

export interface ContextPack {
  selectedItems: ContextItem[];
  rationale: string[];
  budgetTokens: number;
  usedTokens: number;
  finalPack: string; // Serialized context for the worker
}

export interface ContextPacker {
  buildContext(input: ContextPackerInput): Promise<ContextPack>;
}
