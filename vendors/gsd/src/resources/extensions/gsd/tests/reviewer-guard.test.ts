import test from "node:test";
import assert from "node:assert/strict";
import { getReviewerWriteBlockReason, isReviewerWritablePath, shouldBlockReviewerBash, shouldBlockReviewerTool } from "../index.ts";

test("reviewer-write-guard: allows writes under .gsd/", () => {
  const cwd = "/tmp/project";
  assert.equal(isReviewerWritablePath(".gsd/review/notes.md", cwd), true);
  assert.equal(isReviewerWritablePath("/tmp/project/.gsd/notes.md", cwd), true);
});

test("reviewer-write-guard: allows writes under docs/", () => {
  const cwd = "/tmp/project";
  assert.equal(isReviewerWritablePath("docs/review-notes.md", cwd), true);
  assert.equal(isReviewerWritablePath("/tmp/project/docs/adr/proposal.md", cwd), true);
});

test("reviewer-write-guard: blocks product code paths", () => {
  const cwd = "/tmp/project";
  assert.equal(isReviewerWritablePath("src/main.ts", cwd), false);
  assert.equal(isReviewerWritablePath("../other-repo/file.ts", cwd), false);
});

test("reviewer-write-guard: blocks direct graph writes", () => {
  const cwd = "/tmp/project";
  assert.equal(isReviewerWritablePath(".gsd/graph/tasks/T-1.md", cwd), false);
  const reason = getReviewerWriteBlockReason(".gsd/graph/tasks/T-1.md", cwd);
  assert.match(reason, /ROLE-BOUNDARY BLOCKED/i);
  assert.match(reason, /graph_emit_handoff/i);
});

test("reviewer-bash-guard: allows read-only and verification commands", () => {
  assert.equal(shouldBlockReviewerBash("git diff --stat").block, false);
  assert.equal(shouldBlockReviewerBash("rg TODO src").block, false);
  assert.equal(shouldBlockReviewerBash("npm run test:unit").block, false);
  assert.equal(shouldBlockReviewerBash("npm run lint && npm run test:unit").block, false);
});

test("reviewer-bash-guard: blocks mutating git command", () => {
  const result = shouldBlockReviewerBash("git add .");
  assert.equal(result.block, true);
  assert.match(result.reason || "", /read-only git subcommands/i);
});

test("reviewer-bash-guard: blocks unsafe shell patterns", () => {
  const result = shouldBlockReviewerBash("echo hi > docs/note.md");
  assert.equal(result.block, true);
  assert.match(result.reason || "", /pipes|redirects/i);
});

test("reviewer-bash-guard: blocks in-place edits via bash", () => {
  const result = shouldBlockReviewerBash("sed -i 's/a/b/' docs/a.md");
  assert.equal(result.block, true);
  assert.match(result.reason || "", /in-place edit/i);
});

test("reviewer-tool-guard: blocks apply_patch", () => {
  const result = shouldBlockReviewerTool("apply_patch");
  assert.equal(result.block, true);
  assert.match(result.reason || "", /apply_patch/i);
});

test("reviewer-tool-guard: blocks bg_shell", () => {
  const result = shouldBlockReviewerTool("bg_shell");
  assert.equal(result.block, true);
  assert.match(result.reason || "", /bg_shell/i);
});

test("reviewer-tool-guard: blocks async_bash", () => {
  const result = shouldBlockReviewerTool("async_bash");
  assert.equal(result.block, true);
  assert.match(result.reason || "", /async_bash/i);
});

test("reviewer-tool-guard: blocks subagent", () => {
  const result = shouldBlockReviewerTool("subagent");
  assert.equal(result.block, true);
  assert.match(result.reason || "", /subagent/i);
});

test("reviewer-tool-guard: allows unrelated tool names", () => {
  const result = shouldBlockReviewerTool("read");
  assert.equal(result.block, false);
});
