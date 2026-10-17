---
name: impl-loop
description: Preserve implementation ownership and independent review throughout workflow:impl.
---

Mei coordinates; exactly one Elysia implements and repairs; exactly five independent Edens each review one fixed aspect. The graph's six `new` positions create fresh sessions for a new root invocation and reuse those same sessions for every later activation. Reviewers start without inherited conversation history. All share the implementation workspace.

Mei waits while implementation or review is running and does not edit implementation artifacts. Edens review without editing implementation artifacts. Elysia stops editing before returning and remains idle throughout review and report validation. Run all five aspects in parallel for every implementation round. Use tools capable of five concurrent sessions, following the selected adapter and current tool descriptions. Do not silently serialize the group or replace unavailable sessions.

The first implementation receives the task and relevant constraints explicitly. Common review and repair handoffs carry the task or input-document path, relevant constraints, workspace location, loop ID, round number, absolute temporary state directory, implementation artifacts, and check results. Pass proposal or document paths instead of copying their contents. The parallel join preserves the common review handoff alongside the five reports.

Keep coordination notes and validation feedback in the temporary state directory outside the implementation workspace. Save each reviewer's validation feedback separately as `feedback/<aspect>.md`, tagged with its loop ID and round. Give Edens only the common review handoff and access to their own feedback; never include another Eden's report or the consolidated repair request in that handoff. Each Eden retains its own history. Mei receives the joined reports; Elysia receives one validated, consolidated repair request.

A report from an earlier implementation round cannot pass a later round. Technical failures, missing reports, and invalid reports are not PASS. Finish only after all five validated reports pass the current round's unchanged implementation.
