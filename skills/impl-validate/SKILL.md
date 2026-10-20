---
name: impl-validate
description: Aggregate the five review reports, remove unsuitable findings, and select repair or delivery in workflow:impl.
---

Wait for all five reports from the current parallel activation. Verify their findings against the task, constraints, current implementation in the shared workspace, and check results. Remove unsupported, irrelevant, unnecessary, or otherwise unsuitable findings. Merge duplicates and resolve conflicting recommendations using the task and implementation evidence.

Produce one aggregate review report containing the original task, constraints, a verified assessment of all five aspects, and the retained findings with reasons, evidence, and repair scope. Keep the original reports and reasons for removing findings in your own conversation history. Exclude removed findings from the aggregate report sent for repair.

If any retained actionable finding remains, select `rework` with that aggregate report for the same implementer through the task input. All five aspects run again after repair.

Select `passed` when verification of all five current reports leaves no actionable findings. Include the aggregate report, implementation explanation, check results, and externally significant deviations from the requested behavior as evidence for delivery. Base the outcome on the retained findings; keep original reviewer verdicts distinct from your verified assessment.
