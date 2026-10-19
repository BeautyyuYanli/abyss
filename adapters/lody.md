# Lody adapter

将 [Abyss 的会话语义](../SKILL.md)映射到 Lody MCP。具体参数、可用能力和异步完成方式以执行时工具的当前描述为准。

## 会话选择

`run` 动作固定在当前调用栈执行，不调用会话工具，也不接受 `in`。`use` 调用必须声明 `in.ref` 或 `in.new`：`in.ref` 从运行内绑定取得实际 Lody session ID；指向当前 session 时在本地执行所选 workflow，指向其他 session 时使用 `lody_session_chat`。`in.new` 仅在调用位置首次激活时创建，后续激活使用已保存的 session ID 继续同一会话。

创建前通过 `lody_session_create_options` 确认当前 session、机器、agent 配置和本地项目；需要更多候选时使用相应目录查询工具。使用实际目录确认空间关系，不能仅凭项目名、分支名或父子关系认定空间相同。DSL 的 `role` 仍由 prompt 中的 skill 值解释，不自动作为 Lody 的 `agentRoleId`。

## 工作空间

| `in.new.workspace` | Lody 映射 |
| --- | --- |
| `^` | 在调用者的同一实际工作目录中新建 tab。使用 `lody_session_create` 的 `useCurrentSessionAsParent: true` 共享该目录；调用者没有工作空间时创建 chat。 |
| `fork` | 为调用者所在的本地项目创建独立 worktree：`workContext` 使用 `kind: local`、对应的 `projectId` 和 `worktree: true`。调用者没有工作空间时不支持。 |
| `none` | 创建不绑定项目的 chat：`workContext` 使用 `kind: chat`。 |

`useCurrentSessionAsParent: true` 与 `workContext` 不能同时提供。若当前工具拒绝嵌套子会话，只有确认独立本地 session 的目录与调用者实际目录完全相同时，才能用 `workContext` 的 `kind: local`、对应 `projectId` 和 `worktree: false` 创建共享空间的新 tab；不能改用另一个工作目录。无法满足时明确报告不支持。

创建 worktree 后，仍需满足 `workspace: fork` 的文件状态契约，包括首次创建时任务所需的未提交变更和新增工件。仅检出同一分支或 HEAD 不保证这些内容已复制；无法提供该状态时明确报告能力缺口。后续文件修改不自动跨 worktree 同步。

## 历史

工作空间与历史分别核对能力。Lody 的[会话文档](https://lody.ai/docs/session/)说明，Agent 支持原生会话 fork 时，可以复制截至所选已完成回复的历史，并选择当前工作空间或新 worktree；可选目标取决于 Agent 实际报告的能力。

- `history: none`：使用新的独立 session，不带入调用者的旧对话。
- `history: fork`：Agent 和当前可调用工具都支持原生 fork 时，使用该入口复制所需历史，并按 `workspace` 选择创建目标；无法满足所需历史或空间组合时，明确报告当前执行接口不支持该组合。

当前可见的 `lody_session_create`、`lody_session_create_many` 和 `lody session create` CLI 没有暴露原生历史 fork 入口；此处记录当前可调用接口的范围，执行时仍需按最新工具契约核对。父子 session、共享目录和 worktree 都不表示复制了历史。`lody_session_history` 用于读取会话记录，不提供历史 fork；不通过附加旧对话或摘要模拟该能力。

## 投递、绑定与完成

跨 session 的 `use` 创建使用 `lody_session_create`，继续已有 session 使用 `lody_session_chat`；并行组分别使用 `lody_session_create_many` 和 `lody_session_chat_many`，组内每个分支绑定不同的实际 session。所有 `prompt` 参数只填 CLI 生成的完整原文，不追加解释、说明或额外指令。`run` 的本地预览 prompt 不用于派发其他 session。

为异步调用提供 `operationId`，按工具契约接收自动完成通知，不循环轮询操作状态。提交确认只表示请求已接收，不是 workflow 输出。批量调用逐项关联结果与调用位置，不能将一个分支的失败视为其他分支也完成。

创建结果中的实际 session ID 才能绑定到 `in.new.as` 或调用位置；`operationId` 不能作为 session ID。导入到 `context.sessions` 的 `value` 也是实际 Lody session ID，继续调用时将其作为工具的 `sessionId`。投递状态不明时先核对原操作，避免重复发送 prompt；恢复已接受的创建操作时按工具支持的 `operationId` 与 `resume` 契约处理。
