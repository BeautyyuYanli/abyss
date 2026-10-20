---
name: classify-priority
description: Classify work items as P0–P3 using verifiable evidence, actual impact, and recoverability, and order findings in reports.
---

Classify each supplied work item against its stated core goal before deciding its order and effort. Produce priority decisions and a handoff without executing the classified work.

Use verifiable evidence, the actual scope of impact, and recoverability:

- **P0:** Severe, widespread, or irreversible harm to the core goal, safety or security, funds, or permissions. Handle immediately.
- **P1:** The core goal, a key function, or actual delivery is materially blocked. Resolve with priority; do not automatically treat it as an emergency.
- **P2:** A local or secondary difference that does not block the core goal. Verify at low priority, combine with related work, or defer.
- **P3:** A negligible impact such as decoration or formatting. Usually leave it alone.

Base escalation on demonstrated impact. Hypothetical risks, a difference from a preferred implementation, or missing information alone do not establish P0 or P1. Limit verification to facts that could materially change the priority or disposition. If a necessary fact cannot be established from available materials, ask a focused question rather than inventing evidence.

Follow the enclosing action's output contract. For a single work item with `p0`, `p1`, `p2`, and `p3` output ports, return the matching port with a concise natural-language handoff preserving the work item, relevant constraints, decision-relevant evidence, material uncertainty, and the handling recommendation.

For a report of findings, classify each finding, label it P0–P3, and order findings from P0 to P3. Preserve the report's task, constraints, evidence, repair scope, and verdict or selected disposition, then return it through the declared result port. An empty finding list remains empty.

The classification guides routing and tradeoffs. When this is part of a larger task, keep minor classifications within the task's handoff instead of producing separate grading announcements or reports. When the user explicitly asks for classification, provide the result and only the explanation needed to understand it.
