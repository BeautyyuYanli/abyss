---
name: impl-validate
description: Validate the five joined reports and select clarification, repair, or delivery in workflow:impl.
---

Wait for all five reports from the current parallel activation. Check each report's aspect, loop ID, round, explicit PASS or FAILED, and evidence against the current implementation or check results. Reject unsupported findings and requests that unnecessarily expand the task. A missing, invalid, unclear or contradictory report remains unresolved; do not convert it into PASS. Rejected or unclear findings require a corrected report before deciding the round, even when other findings already justify repair. A FAILED report must retain at least one supported, actionable finding within its aspect.

Validate every report before forwarding any finding to Elysia. Deduplicate supported findings and resolve conflicting requests with the responsible reviewers before preparing a repair request. For each aspect, write only that reviewer's validation feedback to `feedback/<aspect>.md` in the temporary state directory. Include the loop ID and round, which own findings are accepted or rejected and why, missing evidence or requested corrections, and any conflict that reviewer must resolve. Explain the relevant implementation constraint or conflicting requirement without forwarding another Eden's report. Mark already valid reports so those reviewers can return them unchanged during clarification. Preserve relevant prior feedback across repair rounds.

If any report still needs clarification or correction, return `clarify` with the original common review handoff, preserving the same loop ID, round, implementation artifacts and checks. Exclude all joined reports and per-reviewer feedback from that text. The graph reuses the same five sessions; each reads only its own updated feedback and returns a report. Do not start rework while a report is missing or unresolved.

Once all five reports are valid, record them and their validation in the coordination notes. If any accepted actionable finding remains, return `rework` directly to the same Elysia with the task, constraints, complete loop state, and one consolidated, prioritized repair request explaining the accepted findings, evidence, and scope. Elysia advances the round during repair; all five aspects run again afterward.

Return `passed` only when all five validated reports are PASS for the current round's unchanged implementation. Include the task, complete loop state, implementation explanation, check results, differences from the original task, and final five reports needed for the implementation report. An earlier round's PASS cannot satisfy this condition.
