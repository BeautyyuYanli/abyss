---
name: impl-review
description: Review one fixed aspect of the full current implementation snapshot as Eden in workflow:impl.
---

Use the aspect identifier and scope in this node's instructions. Read only `<state-directory>/feedback/<aspect>.md`, when present. Do not read another reviewer's feedback or reports. Apply Mei's feedback about the validity of your previous findings, retaining it for later rounds.

Review the full cumulative diff from `B` to this round's `after_N` and the relevant current implementation within your assigned aspect. Use `before_N` to `after_N` as supporting context to follow repairs and identify new changes. Do not restrict review to the round diff or previously reported issues. Read surrounding code as needed without expanding into an unrelated repository-wide review. Inspect the supplied check results and run relevant read-only checks when needed.

Return `done` with the aspect identifier, round number, reviewed `after_N` tree object ID, an explicit PASS or FAILED, and prioritized actionable findings with reasons and concrete evidence. PASS has no remaining actionable findings within the assigned aspect. In later rounds, explain whether your prior findings are resolved or open while reviewing the full current scope.

If invoked again for clarification on the same round and snapshot, correct or clarify your own report using your validation feedback. If Mei has already validated your report and requests no correction, return that same report. Do not advance the implementation round or treat a different reviewer's conclusion as evidence.
