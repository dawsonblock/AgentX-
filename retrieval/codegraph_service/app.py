"""CodeGraphContext Service

Production-grade structural code analysis using tree-sitter.
"""

import os
import json
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from tree_sitter import Language, Parser, Tree, Node
    TREESITTER_AVAILABLE = True
except ImportError:
    TREESITTER_AVAILABLE = False
    logger.warning("tree-sitter not available, using fallback implementation")
    # Define dummy types for type hints when tree-sitter is not available
    Language = Any
    Parser = Any
    Tree = Any
    Node = Any


@dataclass
class Symbol:
    """A code symbol (function, class, variable, etc.)."""
    name: str
    kind: str
    file_path: str
    line_start: int
    line_end: int
    signature: Optional[str] = None
    parent: Optional[str] = None
    children: List[str] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FileNode:
    """A file in the code graph."""
    path: str
    language: str
    symbols: List[Symbol]
    imports: List[str]
    imported_by: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "language": self.language,
            "symbols": [s.to_dict() for s in self.symbols],
            "imports": self.imports,
            "imported_by": self.imported_by
        }


@dataclass
class CallEdge:
    """A call relationship between symbols."""
    caller: str
    callee: str
    file_path: str
    line: int


class TreeSitterManager:
    """Manages tree-sitter parsers for different languages."""
    
    LANGUAGE_MAP = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'tsx',
        '.java': 'java',
        '.go': 'go',
        '.rs': 'rust',
        '.cpp': 'cpp',
        '.c': 'c',
        '.h': 'c',
    }
    
    def __init__(self):
        self.parsers: Dict[str, Parser] = {}
        self.languages: Dict[str, Language] = {}
        self._init_languages()
    
    def _init_languages(self):
        """Initialize language parsers."""
        if not TREESITTER_AVAILABLE:
            return
        
        try:
            # Try to load languages from tree_sitter_languages
            import tree_sitter_python
            import tree_sitter_javascript
            import tree_sitter_typescript
            
            self.languages['python'] = Language(tree_sitter_python.language())
            self.languages['javascript'] = Language(tree_sitter_javascript.language())
            self.languages['typescript'] = Language(tree_sitter_typescript.language_typescript())
            
            for lang_name, language in self.languages.items():
                parser = Parser()
                parser.set_language(language)
                self.parsers[lang_name] = parser
                
        except Exception as e:
            logger.warning(f"Could not initialize tree-sitter languages: {e}")
    
    def get_language_for_file(self, file_path: str) -> Optional[str]:
        """Get language identifier for a file."""
        ext = Path(file_path).suffix.lower()
        return self.LANGUAGE_MAP.get(ext)
    
    def get_parser(self, language: str) -> Optional[Parser]:
        """Get parser for a language."""
        return self.parsers.get(language)
    
    def parse_file(self, file_path: str, content: str) -> Optional[Tree]:
        """Parse a file and return AST."""
        language = self.get_language_for_file(file_path)
        if not language:
            return None
        
        parser = self.get_parser(language)
        if not parser:
            return None
        
        try:
            return parser.parse(bytes(content, 'utf8'))
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return None


class CodeGraphService:
    """Production-grade service for structural code analysis."""

    def __init__(self):
        """Initialize the service."""
        self._indexed_repos: Dict[str, Dict[str, FileNode]] = {}
        self._symbols: Dict[str, Dict[str, Symbol]] = defaultdict(dict)
        self._call_graph: Dict[str, List[CallEdge]] = defaultdict(list)
        self._file_index: Dict[str, Set[str]] = defaultdict(set)
        self.ts_manager = TreeSitterManager()
    
    def index_repo(self, repo_path: str, repo_id: Optional[str] = None) -> Dict[str, Any]:
        """Index a repository for structural analysis.
        
        Args:
            repo_path: Path to repository root
            repo_id: Optional repository identifier (defaults to directory name)
            
        Returns:
            Indexing statistics
        """
        repo_id = repo_id or os.path.basename(repo_path)
        repo_path = os.path.abspath(repo_path)
        
        logger.info(f"Indexing repository: {repo_id} at {repo_path}")
        
        self._indexed_repos[repo_id] = {}
        self._symbols[repo_id] = {}
        self._call_graph[repo_id] = []
        
        files_indexed = 0
        symbols_found = 0
        
        # Walk repository
        for root, dirs, files in os.walk(repo_path):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in {
                '.git', 'node_modules', '__pycache__', '.venv', 
                'venv', 'dist', 'build', '.pytest_cache'
            }]
            
            for filename in files:
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, repo_path)
                
                # Check if it's a source file
                language = self.ts_manager.get_language_for_file(filename)
                if not language:
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read {file_path}: {e}")
                    continue
                
                # Parse and extract symbols
                symbols = self._extract_symbols(file_path, content, language)
                
                file_node = FileNode(
                    path=rel_path,
                    language=language,
                    symbols=symbols,
                    imports=self._extract_imports(content, language),
                    imported_by=[]
                )
                
                self._indexed_repos[repo_id][rel_path] = file_node
                
                # Index symbols
                for symbol in symbols:
                    symbol_key = f"{rel_path}:{symbol.name}"
                    self._symbols[repo_id][symbol_key] = symbol
                    self._file_index[repo_id].add(symbol.name)
                    symbols_found += 1
                
                files_indexed += 1
        
        # Build import relationships
        self._build_import_graph(repo_id)
        
        logger.info(f"Indexed {files_indexed} files, {symbols_found} symbols")
        
        return {
            "repo_id": repo_id,
            "files_indexed": files_indexed,
            "symbols_found": symbols_found,
            "status": "indexed"
        }
    
    def _extract_symbols(self, file_path: str, content: str, language: str) -> List[Symbol]:
        """Extract symbols from file content."""
        symbols = []
        
        if not TREESITTER_AVAILABLE:
            # Fallback: basic regex-based extraction
            return self._extract_symbols_fallback(file_path, content, language)
        
        tree = self.ts_manager.parse_file(file_path, content)
        if not tree:
            return symbols
        
        root = tree.root_node
        
        # Language-specific symbol extraction
        if language == 'python':
            symbols = self._extract_python_symbols(file_path, content, root)
        elif language in ('javascript', 'typescript'):
            symbols = self._extract_js_ts_symbols(file_path, content, root)
        
        return symbols
    
    def _extract_python_symbols(self, file_path: str, content: str, node: Node) -> List[Symbol]:
        """Extract symbols from Python AST."""
        symbols = []
        lines = content.split('\n')
        
        def traverse(node: Node, parent_name: Optional[str] = None):
            if node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = content[name_node.start_byte:name_node.end_byte]
                    signature = self._get_function_signature(node, content)
                    symbol = Symbol(
                        name=name,
                        kind='function',
                        file_path=file_path,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        signature=signature,
                        parent=parent_name
                    )
                    symbols.append(symbol)
                    
                    # Traverse children with this as parent
                    for child in node.children:
                        traverse(child, name)
                        
            elif node.type == 'class_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = content[name_node.start_byte:name_node.end_byte]
                    symbol = Symbol(
                        name=name,
                        kind='class',
                        file_path=file_path,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        parent=parent_name
                    )
                    symbols.append(symbol)
                    
                    # Traverse class body
                    body = node.child_by_field_name('body')
                    if body:
                        for child in body.children:
                            traverse(child, name)
            else:
                for child in node.children:
                    traverse(child, parent_name)
        
        traverse(node)
        return symbols
    
    def _extract_js_ts_symbols(self, file_path: str, content: str, node: Node) -> List[Symbol]:
        """Extract symbols from JavaScript/TypeScript AST."""
        symbols = []
        
        def traverse(node: Node, parent_name: Optional[str] = None):
            if node.type in ('function_declaration', 'method_definition'):
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = content[name_node.start_byte:name_node.end_byte]
                    symbol = Symbol(
                        name=name,
                        kind='function' if node.type == 'function_declaration' else 'method',
                        file_path=file_path,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        parent=parent_name
                    )
                    symbols.append(symbol)
                    
            elif node.type in ('class_declaration', 'class'):
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = content[name_node.start_byte:name_node.end_byte]
                    symbol = Symbol(
                        name=name,
                        kind='class',
                        file_path=file_path,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        parent=parent_name
                    )
                    symbols.append(symbol)
                    
                    # Traverse class body
                    body = node.child_by_field_name('body')
                    if body:
                        for child in body.children:
                            traverse(child, name)
            else:
                for child in node.children:
                    traverse(child, parent_name)
        
        traverse(node)
        return symbols
    
    def _extract_symbols_fallback(self, file_path: str, content: str, language: str) -> List[Symbol]:
        """Fallback symbol extraction using regex."""
        import re
        symbols = []
        lines = content.split('\n')
        
        if language == 'python':
            # Match function definitions
            func_pattern = re.compile(r'^(\s*)def\s+(\w+)\s*\(')
            class_pattern = re.compile(r'^(\s*)class\s+(\w+)')
            
            for i, line in enumerate(lines):
                func_match = func_pattern.match(line)
                if func_match:
                    symbols.append(Symbol(
                        name=func_match.group(2),
                        kind='function',
                        file_path=file_path,
                        line_start=i + 1,
                        line_end=i + 1
                    ))
                
                class_match = class_pattern.match(line)
                if class_match:
                    symbols.append(Symbol(
                        name=class_match.group(2),
                        kind='class',
                        file_path=file_path,
                        line_start=i + 1,
                        line_end=i + 1
                    ))
        
        return symbols
    
    def _get_function_signature(self, node: Node, content: str) -> str:
        """Extract function signature from AST node."""
        params_node = node.child_by_field_name('parameters')
        if params_node:
            return content[node.start_byte:params_node.end_byte]
        return ""
    
    def _extract_imports(self, content: str, language: str) -> List[str]:
        """Extract imports from file content."""
        import re
        imports = []
        
        if language == 'python':
            # Match import statements
            import_pattern = re.compile(r'^(?:from\s+(\S+)\s+import|import\s+(\S+))', re.MULTILINE)
            for match in import_pattern.finditer(content):
                module = match.group(1) or match.group(2)
                if module:
                    imports.append(module)
        
        return imports
    
    def _build_import_graph(self, repo_id: str):
        """Build import relationships between files."""
        files = self._indexed_repos.get(repo_id, {})
        
        for file_path, file_node in files.items():
            for imp in file_node.imports:
                # Find files that might provide this import
                for other_path, other_node in files.items():
                    if other_path == file_path:
                        continue
                    # Check if any symbol in the other file matches the import
                    for symbol in other_node.symbols:
                        if symbol.name in imp:
                            file_node.imported_by.append(other_path)
                            break
    
    def find_symbol(self, repo_id: str, query: str) -> List[Symbol]:
        """Find symbols matching query.
        
        Args:
            repo_id: Repository ID
            query: Symbol name query (partial match supported)
            
        Returns:
            List of matching symbols
        """
        results = []
        query_lower = query.lower()
        
        symbols = self._symbols.get(repo_id, {})
        for symbol_key, symbol in symbols.items():
            if query_lower in symbol.name.lower():
                results.append(symbol)
        
        return results
    
    def get_related_files(self, repo_id: str, file_path: str) -> List[str]:
        """Get files related to a given file.
        
        Args:
            repo_id: Repository ID
            file_path: File path
            
        Returns:
            List of related file paths
        """
        files = self._indexed_repos.get(repo_id, {})
        file_node = files.get(file_path)
        
        if not file_node:
            return []
        
        related = set()
        
        # Files that import this file
        for other_path, other_node in files.items():
            if file_path in other_node.imported_by:
                related.add(other_path)
        
        # Files this file imports
        for imp in file_node.imports:
            for other_path, other_node in files.items():
                for symbol in other_node.symbols:
                    if symbol.name in imp:
                        related.add(other_path)
                        break
        
        return list(related)
    
    def get_callers(self, repo_id: str, symbol_name: str) -> List[Symbol]:
        """Get symbols that call the given symbol.
        
        Args:
            repo_id: Repository ID
            symbol_name: Symbol name
            
        Returns:
            List of calling symbols
        """
        # This would require full call graph analysis
        # Placeholder implementation
        return []
    
    def impact_analysis(self, repo_id: str, target: str) -> Dict[str, Any]:
        """Analyze impact of changing a file or symbol.
        
        Args:
            repo_id: Repository ID
            target: File path or symbol name
            
        Returns:
            Impact analysis result
        """
        files = self._indexed_repos.get(repo_id, {})
        
        affected_files = []
        affected_symbols = []
        test_files = []
        
        # Determine if target is a file or symbol
        if target in files:
            # It's a file
            affected_files = self.get_related_files(repo_id, target)
        else:
            # It's a symbol
            symbols = self.find_symbol(repo_id, target)
            for sym in symbols:
                affected_files.append(sym.file_path)
                affected_symbols.append(sym.name)
        
        # Find test files that might be affected
        for file_path in files:
            if 'test' in file_path.lower():
                for affected in affected_files:
                    if affected.replace('.py', '') in file_path or \
                       affected.replace('.ts', '') in file_path:
                        test_files.append(file_path)
                        break
        
        return {
            "target": target,
            "affected_files": affected_files,
            "affected_symbols": affected_symbols,
            "test_files": test_files
        }


# FastAPI app for service
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="CodeGraph Service", version="1.0.0")
service = CodeGraphService()


class IndexRequest(BaseModel):
    repo_path: str
    repo_id: Optional[str] = None


class QueryRequest(BaseModel):
    repo_id: str
    query: str


@app.post("/index")
def index_repo(req: IndexRequest):
    """Index a repository."""
    try:
        result = service.index_repo(req.repo_path, req.repo_id)
        return result
    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/find-symbol")
def find_symbol(req: QueryRequest):
    """Find symbols matching query."""
    symbols = service.find_symbol(req.repo_id, req.query)
    return {"symbols": [s.to_dict() for s in symbols]}


@app.post("/related-files")
def get_related_files(req: QueryRequest):
    """Get files related to a file."""
    files = service.get_related_files(req.repo_id, req.query)
    return {"files": files}


@app.post("/impact-analysis")
def impact_analysis(req: QueryRequest):
    """Analyze impact of changing a file or symbol."""
    result = service.impact_analysis(req.repo_id, req.query)
    return result


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "tree_sitter_available": TREESITTER_AVAILABLE
    }


# Global service instance for module usage
_service: Optional[CodeGraphService] = None


def get_service() -> CodeGraphService:
    """Get the global service instance."""
    global _service
    if _service is None:
        _service = CodeGraphService()
    return _service
