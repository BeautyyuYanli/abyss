---
name: classify-priority
description: Classify a work item as P0–P3 using verifiable evidence, actual impact, and recoverability for prioritization in workflow:classify.
---

Classify the supplied work item against its stated core goal before deciding its order and effort. This action produces a priority decision and handoff; it does not execute the work.

Use verifiable evidence, the actual scope of impact, and recoverability:

- **P0:** Severe, widespread, or irreversible harm to the core goal, safety or security, funds, or permissions. Handle immediately.
- **P1:** The core goal, a key function, or actual delivery is materially blocked. Resolve with priority; do not automatically treat it as an emergency.
- **P2:** A local or secondary difference that does not block the core goal. Verify at low priority, combine with related work, or defer.
- **P3:** A negligible impact such as decoration or formatting. Usually leave it alone.

Base escalation on demonstrated impact. Hypothetical risks, a difference from a preferred implementation, or missing information alone do not establish P0 or P1. Limit verification to facts that could materially change the priority or disposition. If a necessary fact cannot be established from available materials, ask a focused question rather than inventing evidence.

Return the matching `p0`, `p1`, `p2`, or `p3` output with a concise natural-language handoff preserving the work item, relevant constraints, decision-relevant evidence, material uncertainty, and the handling recommendation. The classification guides routing and tradeoffs. When this is part of a larger task, keep minor classifications internal instead of producing separate grading announcements or reports. When the user explicitly asks for classification, provide the result and only the explanation needed to understand it.
