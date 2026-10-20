---
name: impl-delivery
description: Report externally significant implementation changes after review aggregation finds no remaining issues in workflow:impl.
---

Verify that the aggregate report covers all five completed reviews of the unchanged implementation in the shared workspace and has no retained actionable findings. Use that implementation, the verified review summary, change explanation, and check results as evidence.

Create `.context/impl/YYMMDD-<slug>.md`, creating the directory if needed. Describe the final design and its impact on callers, consumers, or other components. Cover only materially affected areas:

- Interfaces and contracts, including inputs, outputs, errors, and compatibility.
- Underlying data models and storage, including representation, ownership, and invariants.
- Lifecycles, including creation, reuse, state transitions, and cleanup of resources or sessions.
- Other externally observable behavior.

Omit the editing and repair history, internal refactoring, helper or file inventories, and test or review logs and verdicts. Use checks and reviews as evidence for preparing the report. Include deviations from the requested behavior only where they affect the areas above. Skip unaffected areas; a brief completion statement is sufficient when there are no externally significant changes.

Return the report's full contents, without a code-fence wrapper.
