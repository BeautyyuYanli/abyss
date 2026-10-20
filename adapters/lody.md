# Lody adapter

将 [Abyss 的会话语义](../SKILL.md)映射到 Lody MCP。具体参数、可用能力和异步完成方式以执行时工具的当前描述为准。

## 会话配置

创建前通过 `lody_session_create_options` 取得当前 session、机器、agent 配置及本地项目；更多候选使用对应目录查询工具。`instructions` 中的身份指令不自动映射为 Lody 的 `agentRoleId`。

## 工作空间

| `in.new.workspace` | Lody 映射 |
| --- | --- |
| `^` | 在调用者的同一实际工作目录中新建 tab。使用 `lody_session_create` 的 `useCurrentSessionAsParent: true` 共享该目录；调用者没有工作空间时创建 chat。 |
| `fork` | 为调用者所在的本地项目创建独立 worktree：`workContext` 使用 `kind: local`、对应的 `projectId` 和 `worktree: true`。调用者没有工作空间时不支持。 |
| `none` | 创建不绑定项目的 chat：`workContext` 使用 `kind: chat`。 |

`useCurrentSessionAsParent: true` 与 `workContext` 互斥。若宿主拒绝嵌套子会话，可使用对应本地项目及 `worktree: false` 创建独立 session，但须确认其实际目录与调用者相同。

创建 worktree 后，额外核对未提交内容已按 DSL 的 `fork` 契约复制。

## 历史

`history: none` 使用新的独立 session。当前 `lody_session_create` 和 `lody_session_create_many` 未提供原生历史 fork 参数；`history: fork` 仅在执行时工具提供原生入口且满足所选工作空间组合时使用，否则报告不支持。

## 投递与完成

跨 session 创建与继续调用分别使用 `lody_session_create` 和 `lody_session_chat`，并行组使用 `lody_session_create_many` 和 `lody_session_chat_many`。

| Abyss 内容 | Lody 映射 |
| --- | --- |
| `--sessions` / `--sessions-file` 的映射值及展开后的 `ref.id` | Lody 的实际 session ID，原样作为工具参数 `sessionId`。 |
| `in.new.as` | 创建方持有的局部别名，绑定创建结果中的实际 session ID。 |
| 调用侧 `sessions` 中的 `current` | `lody_session_create_options` 返回的调用者当前 session 的实际 ID。 |
| CLI 生成的完整 prompt | 创建或继续调用的 `prompt` 参数，批量调用使用各项对应的 `prompt`。 |
| 一次跨 session 调用或批次 | 一个调用方提供的 `operationId`，用于关联完成通知。 |
| workflow 输出 | 从完成通知中取得目标 turn 的最终回复，按 workflow 输出接口解释。 |

完成通过自动续接通知到达，不循环轮询。批量调用共用一个 `operationId`，各项会话有各自的 `sessionId`；结果按工具返回顺序逐项关联调用位置，失败项独立处理。

恢复已接受的创建操作时，只提交原 `operationId` 和 `resume: true`。

## 会话回收

使用幂等的 `lody_session_archive`，按先子后父的顺序归档。父会话归档会级联子会话，未送达的 Operation Delivery 会挂起直到人工恢复；归档前收齐相关通知并核对级联范围。

终止在途操作由其所属 session 使用 `lody_operation_cancel`，必要时用 `lody_session_cancel` 停止目标 turn。操作取消仅尽力停止目标；取消创建操作不代表会话未创建，需核对实际结果后纳入回收。
