---
name: proposal-draft
description: Create or update the draft artifact as the drafting node of the proposal workflow.
---

For `task` input, create the proposal draft at `.context/proposals/YYMMDD-<slug>.md`, creating the directory if needed. Use the supplied task text or, when no task is specified, the recent conversation.

For `revision` input, locate the existing proposal and requested changes from the incoming handoff, then update that proposal in place.

Discuss uncertain proposal decisions with the user before completing the draft or requested revision.

Return `done` with a natural-language handoff stating the task, draft location, whether this is an initial proposal or a later modification, the required delivery scope, and any affected sections with what changed and why. Carry the necessary task context forward in the text.
