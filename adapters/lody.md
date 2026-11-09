# Lody adapter

将 [Abyss 的会话语义](../SKILL.md)映射到 Lody MCP。具体参数、可用能力和异步完成方式以执行时工具的当前描述为准。

## 会话配置

创建前通过 `lody_session_create_options` 取得当前 session、机器、agent 配置及本地项目；需要更多候选时使用 `lody_agent_config_list`、`lody_agent_role_list` 等目录查询工具。`instructions` 中的身份指令不自动映射为 Lody 的 `agentRoleId`。

`in.new.agent` 指定新会话的 agent 配置与运行参数（形如 `<agent>(<model>, <key>:<value>, ...)`），或指定 Agent Role：

- **Agent 配置与参数描述符**：在目标机器（共享或 fork 本地项目时为调用者所在机器）的 `agentConfigs` 中，按 `name` 或 `agentType` 匹配 `<agent>`（大小写不敏感，允许常见简称或拼写变体，如 `Codex` 匹配 `Codex` / `codex`，`Antigravity` 或 `Antigrativity` 匹配 `Google Antigravity` / `antigravity-acp`），取得 `agentConfigId` 及其 `runConfig`，再将括号内的参数映射为 `lody_session_create` 或 `lody_session_create_many` 的运行参数：
  - `<model>`（首项无键名的模型标识，或 `model:<id>`）：匹配 `runConfig.models` 的 `id` 或 `name`，映射为 `modelId`（及对应的 `configOptionValues.model`）。
  - `reasoning:<level>`：匹配 `runConfig.reasoningEffortValues` 或 `category: "thought_level"` 的配置项，映射为 `reasoningEffort`（及对应的 `configOptionValues`，如 `reasoning_effort`、`thinking_level`）。
  - `priority:<mode>`：`priority:fast` 在目标支持 `runConfig.fastMode` 时映射为 `fastMode: true`（及对应的 `configOptionValues["fast-mode"]: true`）。
  - `permission:<mode>`：在 `runConfig.modes` 中按 `id` 或 `name` 匹配权限模式（大小写不敏感，如 `full` 匹配 `agent-full-access`，`YOLO` 匹配 `yolo`），映射为 `modeId`（及对应的 `configOptionValues.mode`）。
- **Agent Role**：若 `in.new.agent` 指代工作区目录中的 Agent Role，则通过 `lody_agent_role_list` 按名称或 ID 解析 `agentRoleId`（多机器 Role 同时传入 `agentRoleMachineId`）。

未声明 `in.new.agent` 时使用当前/默认 agent 配置。若目标 agent、模型或任一声明参数无法唯一定位或超出目标 `runConfig` 支持范围，报告不支持，不静默忽略参数或回退为其他配置。

## 工作空间

| `in.new.workspace` | Lody 映射 |
| --- | --- |
| `^` | 在调用者的同一实际工作目录中新建 tab。使用 `lody_session_create` 的 `useCurrentSessionAsParent: true` 共享该目录；调用者没有工作空间时创建 chat。 |
| `fork` | 为调用者所在的本地项目创建独立 worktree：`workContext` 使用 `kind: local`、对应的 `projectId` 和 `worktree: true`。调用者没有工作空间时不支持。 |
| `none` | 创建不绑定项目的 chat：`workContext` 使用 `kind: chat`。 |

`useCurrentSessionAsParent: true` 与 `workContext` 互斥。若宿主禁止嵌套子会话（拒绝 `useCurrentSessionAsParent: true`），可为调用者所在的本地项目创建新的 Lody worktree session（`workContext` 使用 `kind: local`、对应的 `projectId` 和 `worktree: true`）作为替代，并确保目标会话可访问任务所需的文件状态或路径；若调用者位于主工作树且实际目录相同，也可使用 `worktree: false`。

创建 worktree 后，额外核对未提交内容已按 DSL 的 `fork` 契约复制。

## 历史

`history: none` 使用新的独立 session。当前 `lody_session_create` 和 `lody_session_create_many` 未提供原生历史 fork 参数；`history: fork` 仅在执行时工具提供原生入口且满足所选工作空间组合时使用，否则报告不支持。

## 投递与完成

跨 session 创建与继续调用分别使用 `lody_session_create` 和 `lody_session_chat`，并行组使用 `lody_session_create_many` 和 `lody_session_chat_many`。`in.new.reuse: false` 的位置在每次激活时都调用创建工具新建 session，不使用 `lody_session_chat` 续接上一轮会话。

| Abyss 内容 | Lody 映射 |
| --- | --- |
| `--sessions` / `--sessions-file` 的映射值及展开后的 `ref.id` | Lody 的实际 session ID，原样作为工具参数 `sessionId`。 |
| `in.new.as` | 创建方持有的局部别名，绑定创建结果中的实际 session ID。 |
| `in.new.agent` | 解析后的 `agentConfigId` 与对应 `runConfig` 参数（`modelId`、`reasoningEffort`、`fastMode`、`modeId`、`configOptionValues`），或 `agentRoleId`。 |
| 调用侧 `sessions` 中的 `current` | `lody_session_create_options` 返回的调用者当前 session 的实际 ID。 |
| CLI 生成的完整 prompt | 创建或继续调用的 `prompt` 参数，批量调用使用各项对应的 `prompt`。 |
| 一次跨 session 调用或批次 | 一个调用方提供的 `operationId`，用于关联完成通知。 |
| workflow 输出 | 从完成通知中取得目标 turn 的最终回复，按 workflow 输出接口解释。 |

完成通过自动续接通知到达，不循环轮询。批量调用共用一个 `operationId`，各项会话有各自的 `sessionId`；结果按工具返回顺序逐项关联调用位置，失败项独立处理。

恢复已接受的创建操作时，只提交原 `operationId` 和 `resume: true`。

## 会话回收

使用幂等的 `lody_session_archive`，按先子后父的顺序归档。`in.new.reuse: false` 的会话在当次调用完成并收齐结果后即可归档；其余 `in.new` 会话在根运行结束时归档。父会话归档会级联子会话，未送达的 Operation Delivery 会挂起直到人工恢复；归档前收齐相关通知并核对级联范围。

终止在途操作由其所属 session 使用 `lody_operation_cancel`，必要时用 `lody_session_cancel` 停止目标 turn。操作取消仅尽力停止目标；取消创建操作不代表会话未创建，需核对实际结果后纳入回收。
