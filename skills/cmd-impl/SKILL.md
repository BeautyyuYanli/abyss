---
name: cmd-impl
description: Run an implementation loop with one persistent Elysia and five independent Eden reviewers in parallel. Use only when the user explicitly names `cmd-impl` or explicitly asks to use this skill's described workflow; do not use it for ordinary coding or implementation requests.
---

# cmd-impl

Mei coordinates implementation and review until all five review aspects pass for the same implementation snapshot. Unless the user specifies another starting point, Elysia implements first.

## Roles and lifecycle

| Role | Responsibility | Lifetime |
| --- | --- | --- |
| Mei | Coordinate agents, record snapshots, validate and consolidate reports, and write the final implementation report. | Entire loop. |
| Elysia | Implement the task and repair accepted review findings. Explicitly load `persona-elysia`. | Create exactly one at the start and reuse her for every implementation and rework turn. |
| Eden × 5 | Review independently, with one fixed aspect per agent. Explicitly load `persona-eden`. | Create exactly five for the first review with no inherited conversation context (`fork_turns: none` or equivalent). Reuse the same five for subsequent rounds and report clarifications. |

Start a fresh set of agents for a new task. Within a loop, each agent retains its own history. Keep the five Eden contexts independent; do not pass one Eden's reports to another.

Mei passes the task and relevant constraints explicitly. If the task is a proposal or document, pass its file path instead of copying its contents. Elysia receives consolidated, validated feedback from Mei. Each Eden receives feedback about the validity of its own report and retains that feedback for later rounds.

Eden agents review without editing implementation artifacts. Mei waits while Elysia or Eden is working and does not edit implementation code herself. Elysia does not modify the implementation while a review round or report validation is in progress.

## Review aspects

Assign exactly one aspect to each Eden. Run all five aspects in every round.

1. **Code and logic hygiene.** Prefer deletion and simplification. Identify dead paths, duplication, unnecessary abstractions, code smells, and custom code that duplicates functionality available in the codebase, current dependencies, or a well-established and actively maintained library.
2. **Correctness and task completion.** Review whether the implementation behaves correctly and fully satisfies the task, proposal, or document.
3. **Test hygiene.** Prefer deleting redundant, meaningless, or misleading tests, especially those introduced during implementation. Identify meaningless negative checks such as "something does not exist" and tests exhibiting the Texas sharpshooter fallacy. Recommend removal before adding or restructuring tests.
4. **Test adequacy.** Review whether meaningful tests sufficiently verify the task's behavior and relevant regressions.
5. **Implementation documentation.** Review the sufficiency of notes, docstrings, comments, and documentation. Treat the proposal as implementation input; do not edit it or request changes to it as documentation.

## Snapshots and diff scope

Choose a unique `<loop-id>` for this invocation. Round `<N>` has two tree snapshots:

| Snapshot | When to capture | Reference |
| --- | --- | --- |
| `before_N` | Immediately before Elysia starts that implementation or rework turn. | `refs/baselines/cmd-impl/<loop-id>/round-<N>-before` |
| `after_N` | After Elysia finishes, before any Eden starts reviewing. | `refs/baselines/cmd-impl/<loop-id>/round-<N>-after` |

The initial baseline `B` is `before_1` and remains fixed throughout the loop.

From the implementation's Git worktree, run `sh <skill-directory>/scripts/snapshot-tree.sh <ref>`. The helper at [scripts/snapshot-tree.sh](scripts/snapshot-tree.sh) saves a tree under a new reference and prints its object ID. It captures tracked changes, deletions, and untracked files that are not ignored, using a temporary copy of the index. It preserves HEAD, real staging, and working files, creates no commits, and refuses to overwrite a reference.

Generate both diffs by comparing recorded trees:

| Diff | Command | Purpose |
| --- | --- | --- |
| Full loop diff | `git diff B after_N --` | Primary review scope: all cumulative changes made during this task. |
| Round diff | `git diff before_N after_N --` | Supporting context: what changed during this implementation or rework turn. |

In these commands, substitute the recorded tree object IDs for `B`, `before_N`, and `after_N`. Use `--stat` for summaries. Comparing two snapshots includes new files without staging them in the real index.

Each Eden reviews the full loop diff and the relevant current implementation within its assigned aspect. Use the round diff to follow repairs and identify new changes; do not limit review to the round diff or previously reported findings. Read surrounding code when needed to assess behavior, without expanding into an unrelated repository-wide review.

All five reviewers must receive the same snapshots and diffs. Provide access to the corresponding implementation and necessary check results; reference names alone are insufficient for a reviewer on another machine. Keep the initial baseline and all round snapshots available through the final report.

## Round procedure

1. **Capture before implementation.** For round 1, record `before_1` and retain it as `B` before allowing Elysia to modify files. For later rounds, record a new `before_N` immediately before sending the rework request.
2. **Implement or repair.** Send Elysia the task for round 1, or one consolidated list of accepted findings for later rounds. After the initial implementation, Elysia edits within the scope of accepted findings. If necessary changes exceed that scope, she explicitly reports what changed and why; Mei includes that information for the responsible Eden in the next review.
3. **Capture after implementation.** Wait for Elysia to finish. Record `after_N`, then generate the full loop diff and round diff.
4. **Review in parallel.** In the first round, create the five Eden agents; in later rounds, continue with the same five. Give each its assigned aspect, task, constraints, round number, snapshot references and object IDs, both diffs, and relevant implementation artifacts. Launch all five before waiting for any report. On later rounds, also ask each Eden to reassess its prior findings using the current snapshot and Mei's prior validation feedback.
5. **Collect and validate.** Wait for all five reports, then apply the report rules below. Do not send partial feedback to Elysia or start rework while a report is missing, invalid, or awaiting clarification.
6. **Decide the next step.** If all five valid reports are PASS for this round's `after_N`, finish the loop. Otherwise, consolidate the accepted findings, advance to round `N + 1`, and repeat from step 1 with the same agents. All five aspects run again after every rework turn.

Use tooling that can run all five Eden reviews concurrently. If native subagent concurrency is insufficient, use parallel session tooling such as Lody: `lody_session_create_many` for the first review and `lody_session_chat_many` to continue with the same five sessions in later rounds. Follow current tool descriptions for role/config discovery, workspace access, and asynchronous completion.

## Reports and feedback validation

Each Eden returns the round number and reviewed `after_N` object ID, an explicit PASS or FAILED result, and prioritized findings with reasons and evidence. A PASS report has no remaining actionable findings within that aspect. On later rounds, explain whether prior findings are resolved or still open, while also reviewing the full current scope.

After collecting all five reports, Mei validates each report before forwarding any findings:

- Check that it concerns the current snapshot and assigned aspect, and that its findings are supported by the implementation or check results.
- Keep feedback focused on the current implementation goal. Reject unsupported findings and requests that unnecessarily expand the scope.
- Return invalid or unclear findings to the corresponding Eden with the reason for rejection or the missing evidence. Obtain a corrected report before deciding the round; do not turn a missing or invalid report into PASS.
- Deduplicate accepted findings and resolve conflicting requests with the responsible reviewers before sending one consolidated rework request to Elysia.

## Completion

Finish only when all five validated reports are PASS for the same `after_N`. A PASS from an earlier snapshot does not satisfy a later round.

Mei writes `.context/impl/YYMMDD-<slug>.md`, creating the directory if needed. Describe the implementation, major additions and deletions, and any differences from the original task. Use the full loop diff from `B` to the final `after_N` as evidence; include those references and object IDs, relevant check results, and the final review outcomes.

Send the final report's full contents to the conversation without a code-fence wrapper.
