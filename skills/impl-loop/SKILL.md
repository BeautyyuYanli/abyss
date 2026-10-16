---
name: impl-loop
description: Preserve ownership, snapshot consistency, and independent review throughout workflow:impl.
---

Mei coordinates; exactly one Elysia implements and repairs; exactly five independent Edens each review one fixed aspect. The graph's six `new` positions create fresh sessions for a new root invocation and reuse those same sessions for every later activation. Reviewers start without inherited conversation history. All share the implementation workspace.

Mei waits while implementation or review is running and does not edit implementation artifacts. Edens review without editing implementation artifacts. Elysia stops editing before returning and remains idle throughout review and report validation. Run all five aspects in parallel for every implementation snapshot. Use tools capable of five concurrent sessions, such as Lody's create-many and chat-many tools, following their current descriptions. Do not silently serialize the group or replace unavailable sessions.

Implementation and common review handoffs carry the task or input-document path, relevant constraints, repository location, loop ID, round number, absolute temporary state directory, fixed initial baseline `B`, and the available per-round snapshot references and tree object IDs. Include relevant implementation artifacts and check results. Pass proposal or document paths instead of copying their contents. The parallel join preserves the common review handoff alongside the five reports.

Keep coordination notes, diffs, and validation feedback in the temporary state directory outside the implementation worktree so they do not enter snapshots. Save each reviewer's validation feedback separately as `feedback/<aspect>.md`, tagged with its round and snapshot. Give Edens only the common review handoff and access to their own feedback; never include another Eden's report or the consolidated repair request in that handoff. Each Eden retains its own history. Mei receives the joined reports; Elysia receives one validated, consolidated repair request.

Keep `B` and every round's snapshots accessible through delivery. A report from an older snapshot cannot pass a later round. Technical failures, missing reports, and invalid reports are not PASS. Finish only after all five validated reports pass the same `after_N`.
