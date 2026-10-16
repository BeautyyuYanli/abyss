---
name: impl-delivery
description: Write and return the final implementation report after workflow:impl passes all five reviews.
---

Verify that all five validated final reports are PASS for the same `after_N`. Use the full cumulative diff from `B` to that final tree as evidence.

Create `.context/impl/YYMMDD-<slug>.md`, creating the directory if needed. Describe the implementation, major additions and deletions, and any differences from the original task. Include the initial baseline and final snapshot references and tree object IDs, relevant check results, and each final review outcome. Keep all round snapshots available through this report.

Return `done` with the report's full contents, without a code-fence wrapper.
