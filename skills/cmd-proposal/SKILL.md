---
name: cmd-proposal
description: Create a proposal using the file-writing workflow described in this skill. Use only when the user explicitly names `cmd-proposal` or explicitly asks to use this skill's described workflow; do not use it for ordinary planning, design, or proposal requests.
---
Write a proposal with name `YYMMDD-<slug>.md` at folder `.context/proposals/` (create if not existed) for the given task. If no task specified, it should be from the last conversation.

Focus the proposal on the implementation required to satisfy the task: business logic, code changes, interfaces, data models, and infrastructure schemas only when they are part of the implementation.

Do not add deployment plans, rollout or rollback procedures, validation or verification sections, operational runbooks, maintenance instructions, or user and operator manuals unless the user explicitly requests them. Do not add generic checklists or post-implementation guidance.

Do not leave modifing history or questions in the proposal, discuss with the user to determine any uncertain points before finishing the proposal.

After completing the first draft, spawn exactly one subagent with the full conversation context. Explicitly tell the subagent to load `persona-mei` and review only whether the proposal is overengineered, identifying concrete simplifications that preserve the user's requirements. Evaluate the review, accept only relevant findings, and perform exactly one simplification pass on the proposal. Do not start another review loop.

Only after the simplification pass, send the full final proposal in the conversation without a ```...``` wrapper. Do not send the first draft or the subagent's review. For later user-requested modifications, send the updated sections and accompany them with a concise prose explanation of which sections changed, what changed, and why. Do not show original-versus-modified blocks or use diff-like formatting.
