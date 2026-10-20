---
name: impl-review
description: Review one fixed aspect of the current implementation in workflow:impl.
---

Use the aspect identifier and scope in the effective workflow and action instructions. Use your own conversation history to revisit previous findings and reports. Do not read another reviewer's feedback or reports.

Review the current implementation in the shared workspace against the full task within your assigned aspect. Use the task and change explanation without restricting review to previously reported issues. Read surrounding code as needed without expanding into an unrelated repository-wide review. Inspect the supplied check results and run relevant read-only checks when needed.

Return a report with the aspect identifier, an explicit PASS or FAILED, and actionable findings with reasons and concrete evidence. PASS has no remaining actionable findings within the assigned aspect. After repairs, explain whether your prior findings are resolved or open while reviewing the full current scope.
