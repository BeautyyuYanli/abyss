---
name: impl-snapshot
description: Capture before and after tree snapshots and prepare implementation or review handoffs for workflow:impl.
---

Use [scripts/snapshot-tree.sh](scripts/snapshot-tree.sh) from the implementation's Git worktree:

```sh
sh <skill-directory>/scripts/snapshot-tree.sh <ref>
```

The helper captures tracked changes, deletions, and untracked files that are not ignored. It uses a temporary copy of the index, preserves HEAD, real staging and working files, creates no commits, and refuses to overwrite a reference. Use the returned tree object ID, not a commit or the live worktree, for comparisons.

For `task` input, obtain the task and relevant constraints from the input or recent conversation. Choose a unique loop ID, start round 1, and create an absolute temporary state directory outside the worktree. Record the task and state there. Immediately before dispatching Elysia, capture `before_1` under `refs/baselines/impl/<loop-id>/round-1-before`; retain its object ID as the fixed initial baseline `B`.

For `rework` input, preserve the task, state directory, `B`, and accepted consolidated findings. Advance the round number, then capture `before_N` immediately before dispatching the same Elysia under `refs/baselines/impl/<loop-id>/round-<N>-before`. Return `done` with the full implementation handoff and accepted repair scope. For the first round, return the same handoff with the original task as the implementation scope.

For `implementation` input, wait for Elysia's completed turn, then capture `after_N` under `refs/baselines/impl/<loop-id>/round-<N>-after` before any review starts. Generate the cumulative diff with `git diff B after_N --` and the round diff with `git diff before_N after_N --`, substituting the recorded tree IDs. Save both outside the worktree, and use `--stat` for summaries. The cumulative diff is the primary review scope.

Record the snapshots, check results, implementation summary, task differences, and necessary changes beyond the accepted repair scope in the coordination notes. Return `done` with a fresh common review handoff containing the task, constraints, loop state, snapshot references and IDs, both accessible diffs, current implementation locations, check results, and the feedback directory. Include neutral explanations of changes beyond the repair scope for reassessment. Exclude reviewer reports and the consolidated findings given to Elysia; each Eden receives its own validation feedback from its separate file.

On failure, resolve the snapshot or diff error before returning; do not continue with an uncaptured or mismatched tree.
