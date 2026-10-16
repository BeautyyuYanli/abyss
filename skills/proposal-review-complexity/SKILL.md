---
name: proposal-review-complexity
description: Review only unnecessary proposal complexity as the single review node of the proposal workflow.
---

Read the draft at the location described in the incoming handoff, using the task context supplied in that handoff. Review only whether the proposal is overengineered, identifying concrete simplifications that preserve the user's requirements. Leave the proposal file unchanged.

Return `done` with natural-language text that preserves the incoming task, draft location, delivery scope and change explanation, then adds the complexity review, concrete simplifications and their reasons. State clearly when no relevant simplifications are found.
