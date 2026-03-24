"""Dummy worker for testing.

Returns a simple patch for testing the system without LLM calls.
"""

from typing import Dict, Any

from .interface import Worker


class DummyWorker(Worker):
    """Dummy worker that returns a simple patch."""
    
    def run(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Return a dummy patch."""
        return {
            "patch": """diff --git a/example.txt b/example.txt
new file mode 100644
--- /dev/null
+++ b/example.txt
@@ -0,0 +1 @@
+# Example file created by AgentX dummy worker
+hello world
""",
            "logs": "Dummy worker executed successfully",
            "artifacts": [],
            "summary": "Created example.txt with hello world"
        }
