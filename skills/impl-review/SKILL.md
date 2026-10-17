---
name: impl-review
description: Review one fixed aspect of the current implementation as Eden in workflow:impl.
---

Use the aspect identifier and scope in this node's instructions. Read only `<state-directory>/feedback/<aspect>.md`, when present. Do not read another reviewer's feedback or reports. Apply Mei's feedback about the validity of your previous findings, retaining it for later rounds.

Review the current implementation against the full task within your assigned aspect. Use the supplied artifacts and change explanation without restricting review to previously reported issues. Read surrounding code as needed without expanding into an unrelated repository-wide review. Inspect the supplied check results and run relevant read-only checks when needed.

Return `done` with the aspect identifier, loop ID, round number, an explicit PASS or FAILED, and prioritized actionable findings with reasons and concrete evidence. PASS has no remaining actionable findings within the assigned aspect. In later rounds, explain whether your prior findings are resolved or open while reviewing the full current scope.

If invoked again for clarification in the same round on the unchanged implementation, correct or clarify your own report using your validation feedback. If Mei has already validated your report and requests no correction, return that same report. Do not advance the implementation round or treat a different reviewer's conclusion as evidence.
