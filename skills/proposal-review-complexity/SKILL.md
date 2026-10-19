---
name: proposal-review-complexity
description: Review only unnecessary proposal complexity as the single review node of the proposal workflow.
---

For `draft` input, read the initial draft at the location described in the incoming handoff, using the supplied task context.

For `revision` input, read the existing proposal together with the requested edits. Review the intended result with those edits, and carry the edits forward as pending work. The delivery scope is the updated sections with a concise explanation of the changes.

Review only whether the proposal is overengineered, identifying concrete simplifications that preserve the user's requirements. Leave the proposal file unchanged.

Return natural-language text that preserves the task, proposal location, delivery scope, pending requested edits and any existing change explanation, then adds the complexity review, concrete simplifications and their reasons. State clearly when no relevant simplifications are found.
