---
name: coding-rules
description: General coding rules. Read and apply this skill whenever a task involves coding.
---

# Coding Rules

Apply these rules to the code involved in the current task. Follow the project's conventions for language features, documentation, tooling, and test organization.

## Notes for Agent (must-check)

Before changing source code, you MUST read the relevant documentation and surrounding comments in the affected area. These notes contain required context (invariants, edge cases, trade-offs) and are treated as part of the spec.

In this skill, “notes” means docstrings or equivalent documentation used by the project, plus relevant block or inline comments.

Look for:

- Module or file documentation
- Documentation on classes, types, and functions/methods
- Paragraph/block comments for non-obvious logic

### What to write where

- Keep notes scoped: module notes cover module-wide context, class/type notes cover context shared by that type, function/method notes cover behavioural contracts, and paragraph/block comments cover local “why”. Avoid duplicating the same content across scopes unless repetition prevents misuse.
- **Module or file documentation**: purpose, boundaries, key invariants, and “gotchas” that a new reader must know before editing.
  - Include cross-links to the key collaborators (modules/services) when discovery is otherwise hard.
  - Prefer stable facts (invariants, contracts) over ephemeral “today we…” notes.
- **Class or type documentation**: responsibility, lifecycle, invariants, and how it should be used (or not used).
  - If the class or type intentionally maintains state, note what state exists and which operations mutate it.
  - If concurrency/async assumptions matter, state them explicitly.
- **Function/method documentation**: behavioural contract.
  - Document contract details that are not clear from signatures or types, including argument constraints, return shape, side effects, and errors (whether raised or returned).
  - Add examples only when they prevent misuse.
- **Paragraph/block comments**: explain *why* (trade-offs, historical constraints, surprising edge cases), not what the code already states.
  - Keep comments adjacent to the logic they justify; delete or rewrite comments that no longer match reality.

### Rules (must follow)

- **Before working**
  - Read the notes in the area you’ll touch; treat them as part of the spec.
  - Use the code to establish actual behavior. Use requirements and documented contracts to establish intended behavior. If they conflict, investigate relevant callers, tests, and change history as needed to determine whether the implementation or the notes need correction before updating either.
  - If important intent/invariants/edge cases are missing, add them in the nearest appropriate notes (module for overall scope, function for behaviour).
- **During working**
  - Keep the notes in sync as you discover constraints, make decisions, or change approach.
  - If you move/rename responsibilities across modules, types, or functions, update the affected notes so readers can still find the “why” and the invariants.
  - Record stable, non-obvious edge cases and trade-offs in the nearest appropriate notes. Keep temporary verification plans and results in the task record or change description.
  - Keep the notes **coherent**: integrate new findings into the relevant documentation and comments; avoid append-only “recent fix” / changelog-style additions.
- **When finishing**
  - Update the notes to reflect the resulting behavior, its rationale, and any new stable constraints or edge cases. Keep affected tests consistent with the intended contract.
  - Remove or rewrite any comments that could be mistaken as current guidance but no longer apply.
  - Keep notes concise and accurate; they are meant to prevent repeated rediscovery.

## Coding Style

### General Rules

- Use typing and static analysis where supported by the language and project.
- Run applicable checks after each complete logical change and before finishing. Avoid introducing new type errors or static analysis failures.
- When integrating with, implementing, or mocking a dependency, confirm its API shape and runtime behavior using available source code, official documentation, type definitions, or schemas. Resolve ambiguities with focused verification instead of guessing from names alone.
- Prefer simple functions over small “utility classes” for lightweight helpers.
- Implement language-specific hooks or special methods only when needed and consistent with existing project patterns.
- Keep code readable and explicit—avoid clever hacks.

### Testing

- Use the project's configured test commands and run the tests relevant to the change, including any required checks.
- Follow the project's existing test locations and organization. If no convention exists, choose a consistent, discoverable layout suited to the project.

#### Local Tests

- Use local tests to verify stable, externally observable behavior quickly without real external services.
- Keep code, documentation, comments, and affected tests consistent. Tests of intended behavior should remain valid after internal refactors that preserve that behavior.
- Local tests should verify, as relevant to the contract:
  - what callers and downstream code can observe and rely on
  - how the unit is expected to use its dependencies at the boundary
  - how the unit handles dependency success, failure, empty responses, malformed responses, and documented error cases
  - documented invariants, error mapping, and output/input shape guarantees
- When asserting dependency interactions, assert only the parts of the request or response that are part of the real boundary contract. Do not over-specify incidental details that callers or dependencies do not rely on.
- It is acceptable to mock dependencies in local tests, but only when the mock represents a real contract, schema, documented behavior, or known regression.
- Where the language and tooling support it, tests may use narrowly scoped type-check suppressions to exercise intentionally invalid inputs that static typing would normally reject. Limit each suppression to the smallest supported scope around the invalid expression.
- Choose the test level according to the real components and environment needed to verify the behavior. Deterministic behavior such as serialization can be tested locally using the actual implementation. Claims about real integration, external wiring, or third-party runtime behavior require tests that exercise the relevant real components; mocked dependency behavior is not evidence of those properties.
- Meaningless local tests include:
  - tests that only mirror the current implementation or must be updated whenever internal code changes even though the contract did not change
  - tests of private helpers, local variables, temporary state, internal branching, or exact internal call order unless those details are part of the published contract
  - tests with mocked dependency behavior that is invented only to make the current implementation pass
  - tests that add no value beyond static type checking or linting

### Logging & Errors

- Use the project's logging facilities for diagnostic messages. Preserve standard output when it is part of the program's intended interface, such as CLI results or pipeline data.
