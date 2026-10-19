---
name: impl-implement
description: Implement the task or repair Mei's accepted findings as Elysia in workflow:impl.
---

Read the task, constraints, and referenced proposal or document from the incoming handoff. For `task` input, start round 1 with a fresh loop ID and an absolute temporary state directory outside the implementation workspace, then implement the original task. For `rework` input, preserve the loop ID and state directory, advance the round, and edit within Mei's consolidated accepted findings. If necessary changes exceed that scope, report exactly what changed and why for reassessment in the next review.

Run checks appropriate to the changes. Return a common review handoff containing the task, constraints, workspace location, loop ID, round, state directory, implementation artifacts, files added/changed/deleted, check commands and results, differences from the original task, and neutral explanations of necessary changes beyond the repair scope. Exclude the consolidated repair request and reviewer reports from this handoff. Stop editing before returning; wait for Mei's next repair request.
