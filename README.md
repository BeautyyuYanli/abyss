# abyss

Reusable agent skills for coding conventions, development workflows, and personas.

## Skills

| Skill | Purpose |
| --- | --- |
| [coding-rules](skills/coding-rules/SKILL.md) | Coding, documentation, and testing conventions. |
| [cmd-impl](skills/cmd-impl/SKILL.md) | Implementation and review with Elysia and five independent Eden reviewers. |
| [cmd-merge](skills/cmd-merge/SKILL.md) | Commit a worktree and merge it into the main worktree. |
| [cmd-proposal](skills/cmd-proposal/SKILL.md) | Write a proposal and review it for unnecessary complexity. |
| [cmd-vscode-link](skills/cmd-vscode-link/SKILL.md) | Create a clickable VS Code Remote SSH link using a local network address. |
| [persona-eden](skills/persona-eden/SKILL.md) | Code reviewer persona. |
| [persona-elysia](skills/persona-elysia/SKILL.md) | Implementation persona. |
| [persona-mei](skills/persona-mei/SKILL.md) | Research and coordination persona. |

## Usage

Each directory under `skills/` is a complete skill. Copy the desired directories
into your agent's skills directory, preserving their supporting files.

- Install `persona-elysia` and `persona-eden` alongside `cmd-impl`.
- Install `persona-mei` alongside `cmd-proposal`.
- `cmd-impl` includes `scripts/snapshot-tree.sh`; keep it with the skill.

These skills are copied from the existing local skill collection. Their contents
and supporting files are preserved.
