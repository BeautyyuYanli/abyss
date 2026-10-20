---
name: impl-loop
description: Preserve implementation ownership and independent review throughout workflow:impl.
---

The coordinator directs exactly one implementer, who implements and repairs, and exactly five independent reviewers, who each review one fixed aspect. The graph's six `new` positions create fresh sessions for a new root invocation and reuse those same sessions for every later activation. Reviewers start without inherited conversation history. All share the implementation workspace.

The coordinator waits while implementation or review is running and does not edit implementation artifacts. Reviewers review without editing implementation artifacts. The implementer stops editing before returning and remains idle throughout review and report validation. Run all five aspects in parallel for every implementation round. Use tools capable of five concurrent sessions, following the selected adapter and current tool descriptions. Do not silently serialize the group or replace unavailable sessions.

Implementation requests use one task input, carrying the task, relevant constraints, and any verified aggregate review report and repair scope. All agents inspect the current implementation directly in the shared workspace. Common review handoffs carry the task or input-document path, relevant constraints, change explanation, and check results. Pass proposal or document paths instead of copying their contents. The parallel join preserves the common review handoff alongside the five reports.

Each agent retains its own conversation history. The coordinator keeps the collected reports and verification decisions in its conversation. Give reviewers only the common review handoff. Never include another reviewer's report or conclusions, or the aggregate review report, in that handoff. Each reviewer uses its own history to revisit its findings. The coordinator removes unsuitable findings, merges the remaining findings, and sends the resulting aggregate report to the implementer when repairs are needed.

Associate reports with the current parallel activation through the workflow's execution state. Reports about an earlier implementation cannot substitute for reviews of the current implementation. Technical failures and missing reports mean review is incomplete. Finish only after all five current reports have been collected and their verified aggregate contains no remaining actionable findings about the unchanged implementation in the shared workspace.
