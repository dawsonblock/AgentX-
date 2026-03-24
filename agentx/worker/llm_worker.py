"""Bounded LLM worker with Kimi API integration.

This worker implements a bounded execution loop that:
- Uses only allowed tools
- Has maximum step limits
- Never executes raw shell commands
- Always produces a git diff
"""

import json
import os
from typing import Dict, Any, List

from core.config import Settings
from core.errors import PolicyDenied, LLMError
from core.logging import get_logger
from runtime.policies import check_tool, check_steps, MAX_STEPS
from worker.base_worker import BaseWorker, WorkerResult
from worker.tools.file_read import read_file
from worker.tools.search import search, search_files
from worker.tools.git_tools import git_diff, git_status
from worker.tools.test_runner import run_tests

logger = get_logger(__name__)


# Tool registry - only these tools are allowed
TOOLS = {
    "read_file": read_file,
    "search": search,
    "search_files": search_files,
    "run_tests": run_tests,
    "git_diff": git_diff,
    "git_status": git_status
}


def build_system_prompt() -> str:
    """Build the system prompt for the LLM."""
    return """You are a coding assistant that helps modify codebases.

Your goal is to analyze the task, explore the codebase, and make necessary changes.

AVAILABLE TOOLS:
- read_file(path): Read a file's content
- search(root, query): Search for text in the repository
- search_files(root, pattern): Find files matching a pattern
- run_tests(root, test_path=""): Run tests
- git_diff(root): Get current git diff
- git_status(root): Get git status

RULES:
1. You can only use the tools listed above
2. You have a maximum of 20 steps
3. You can read files, search, and run tests
4. To modify a file, use type="edit" with path and content
5. When done, use type="finish"
6. Always provide your reasoning

OUTPUT FORMAT:
Respond with a JSON object:
{
    "type": "tool" | "edit" | "finish",
    "reasoning": "Your reasoning here",
    "tool": "tool_name",  // if type="tool"
    "args": {},  // if type="tool"
    "path": "file_path",  // if type="edit"
    "content": "file_content"  // if type="edit"
}"""


def build_prompt(state: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build the conversation prompt from state.
    
    Args:
        state: Current state with task, context, notes, last action
        
    Returns:
        List of message dicts for the API
    """
    messages = [
        {"role": "system", "content": build_system_prompt()}
    ]
    
    # Add context files (just paths, not full content to save tokens)
    context_summary = ""
    if state.get("context"):
        context_summary = "Available files:\n"
        for ctx in state["context"][:10]:
            context_summary += f"- {ctx['path']}\n"
    
    # Build user message
    user_msg = f"""TASK: {state['task']}

{context_summary}

STEP: {state.get('step', 0)} of {MAX_STEPS}

NOTES:
{chr(10).join(state.get('notes', [])) if state.get('notes') else '(no notes yet)'}

LAST ACTION:
{json.dumps(state.get('last', {}), indent=2) if state.get('last') else '(just started)'}

What do you do next?"""
    
    messages.append({"role": "user", "content": user_msg})
    return messages


def llm_call(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """Call the Kimi API.
    
    Args:
        messages: List of message dicts with role and content
        
    Returns:
        Parsed JSON response
        
    Raises:
        LLMError: If API call fails
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise LLMError("openai package not installed. Run: pip install openai")
    
    api_key = Settings.KIMI_API_KEY
    if not api_key:
        raise LLMError("KIMI_API_KEY not set in environment")
    
    client = OpenAI(
        api_key=api_key,
        base_url=Settings.KIMI_BASE_URL
    )
    
    try:
        logger.debug(f"Calling Kimi API with {len(messages)} messages")
        
        response = client.chat.completions.create(
            model=Settings.KIMI_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        if not content:
            raise LLMError("Empty response from Kimi API")
        
        # Parse JSON response
        try:
            result = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from LLM: {content[:200]}")
            raise LLMError(f"LLM returned invalid JSON: {e}")
        
        logger.debug(f"LLM response: {result.get('type', 'unknown')}")
        return result
        
    except Exception as e:
        if isinstance(e, LLMError):
            raise
        logger.error(f"Kimi API error: {e}")
        raise LLMError(f"Kimi API error: {e}")


class LLMWorker(BaseWorker):
    """Bounded LLM worker that uses Kimi API."""
    
    def execute(self, task: str, context: List[Dict[str, Any]], worktree: str) -> WorkerResult:
        """Execute the bounded LLM loop.
        
        Args:
            task: Task description
            context: Context files
            worktree: Worktree path
            
        Returns:
            WorkerResult with diff
        """
        state = {
            "task": task,
            "context": context,
            "notes": [],
            "last": None,
            "step": 0,
            "files_modified": 0
        }
        
        logger.info(f"Starting LLM worker for task: {task[:50]}...")
        
        for step in range(MAX_STEPS):
            state["step"] = step + 1
            
            # Check step limit
            try:
                check_steps(step)
            except PolicyDenied:
                state["notes"].append(f"Reached max steps ({MAX_STEPS})")
                break
            
            # Build and send prompt
            messages = build_prompt(state)
            
            try:
                action = llm_call(messages)
            except LLMError as e:
                logger.error(f"LLM call failed: {e}")
                state["notes"].append(f"LLM error: {e}")
                break
            
            # Process action
            action_type = action.get("type")
            reasoning = action.get("reasoning", "(no reasoning provided)")
            
            logger.info(f"Step {step+1}: {action_type} - {reasoning[:50]}...")
            
            if action_type == "tool":
                tool_name = action.get("tool")
                tool_args = action.get("args", {})
                
                # Validate tool
                try:
                    check_tool(tool_name)
                except PolicyDenied as e:
                    state["last"] = {"error": str(e)}
                    state["notes"].append(f"Tool denied: {tool_name}")
                    continue
                
                # Execute tool
                tool_func = TOOLS[tool_name]
                
                # Inject worktree for tools that need it
                if tool_name in ("search", "search_files", "run_tests", "git_diff", "git_status"):
                    tool_args["root"] = worktree
                
                try:
                    result = tool_func(**tool_args)
                    state["last"] = {"tool": tool_name, "result": str(result)[:1000]}
                    state["notes"].append(f"Used {tool_name}: {reasoning[:50]}...")
                except Exception as e:
                    state["last"] = {"tool": tool_name, "error": str(e)}
                    state["notes"].append(f"{tool_name} failed: {e}")
                
            elif action_type == "edit":
                path = action.get("path")
                content = action.get("content")
                
                if not path:
                    state["last"] = {"error": "No path provided for edit"}
                    continue
                
                # Ensure path is within worktree
                full_path = os.path.join(worktree, path.lstrip("/"))
                if not full_path.startswith(worktree):
                    state["last"] = {"error": "Path escape attempt blocked"}
                    state["notes"].append(f"Blocked path escape: {path}")
                    continue
                
                # Write file
                try:
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w") as f:
                        f.write(content)
                    
                    state["files_modified"] = state.get("files_modified", 0) + 1
                    state["last"] = {"edit": path, "size": len(content)}
                    state["notes"].append(f"Edited {path}: {reasoning[:50]}...")
                    logger.info(f"Edited file: {path}")
                except Exception as e:
                    state["last"] = {"edit": path, "error": str(e)}
                    state["notes"].append(f"Failed to edit {path}: {e}")
                
            elif action_type == "finish":
                state["notes"].append(f"Finished: {reasoning}")
                logger.info(f"Worker finished: {reasoning}")
                break
            
            else:
                state["last"] = {"error": f"Unknown action type: {action_type}"}
                state["notes"].append(f"Unknown action: {action_type}")
        
        # Generate final diff
        diff = git_diff(worktree)
        
        # Get status for summary
        status = git_status(worktree)
        files_modified = len([l for l in status.split("\n") if l.strip()])
        
        logger.info(f"Worker complete. Diff size: {len(diff)} chars, Files modified: {files_modified}")
        
        return WorkerResult(
            diff=diff,
            summary=f"Modified {files_modified} files in {state['step']} steps",
            files_modified=files_modified,
            notes=state["notes"]
        )
