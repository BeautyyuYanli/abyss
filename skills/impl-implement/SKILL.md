---
name: impl-implement
description: Implement the task or repair verified aggregate review findings in workflow:impl.
---

Read the task, constraints, referenced proposal or document, and any supplied verified aggregate review report from the incoming handoff. Implement the requested work in the shared workspace within the supplied scope. If necessary changes exceed that scope, report exactly what changed and why for reassessment in the next review.

Run checks appropriate to the changes. Return a common review handoff containing the task, constraints, change explanation, check commands and results, differences from the original task, and neutral explanations of necessary changes beyond the supplied scope. Reviewers inspect the current implementation in the shared workspace. Exclude the aggregate review report and individual reviewer reports from this handoff. Stop editing before returning; wait for the coordinator's next task.
