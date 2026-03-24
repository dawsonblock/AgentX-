import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createReviewerTools } from "../graph/reviewer-tools.ts";

test("reviewer-handoff-tool: emits structured handoff artifact in one command", async () => {
  const dir = mkdtempSync(join(tmpdir(), "gsd-graph-"));
  try {
    const tools = createReviewerTools(dir, "reviewer-test") as any[];
    const handoffTool = tools.find((t) => t.name === "graph_emit_handoff");
    assert.ok(handoffTool, "graph_emit_handoff tool is registered");

    const result = await handoffTool.execute("tc-1", {
      attemptedAction: "Create T-001 in .gsd/graph/tasks",
      requiredRole: "coder",
      reason: "Reviewer role cannot write .gsd/graph/*",
      payload: "Create task T-001 for stale summary cleanup and sync PROJECT.md/STATE.md.",
      evidence: [
        'write denied: "Reviewer role cannot use write"',
        "graph_create_task not available in reviewer tool set",
      ],
    });

    const text = result.content?.[0]?.text ?? "";
    assert.match(text, /ROLE-BOUNDARY BLOCKED handoff recorded/i);

    const handoffsDir = join(dir, "handoffs");
    const files = readdirSync(handoffsDir).filter((f) => f.endsWith(".md"));
    assert.equal(files.length, 1, "one handoff artifact was written");

    const content = readFileSync(join(handoffsDir, files[0]), "utf-8");
    assert.match(content, /^---\nid: H-/m);
    assert.match(content, /from_role: reviewer/m);
    assert.match(content, /to_role: coder/m);
    assert.match(content, /## Why blocked/m);
    assert.match(content, /## Minimal handoff payload/m);
    assert.match(content, /## Evidence/m);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
