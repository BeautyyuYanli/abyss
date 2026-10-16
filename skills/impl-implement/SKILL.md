---
name: impl-implement
description: Implement the task or repair Mei's accepted findings as Elysia in workflow:impl.
---

Read the task, constraints, and referenced proposal or document from the incoming handoff. Implement the original task in round 1. In later rounds, edit within Mei's consolidated accepted findings. If necessary changes exceed that scope, report exactly what changed and why so Mei can include it in the next review.

Run checks appropriate to the changes. Return `done` with the task, loop state and before snapshot intact, implementation summary, files added/changed/deleted, check commands and results, differences from the original task, and any necessary changes beyond the repair scope. Stop editing before returning; wait for Mei's next repair request.
