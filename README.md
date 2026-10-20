# Abyss

Abyss 是一个编排 agent 进行多步骤工作的 workflow 框架，以纯 skill 的方式即可运行。

## 快速开始

将仓库下载到本机，保留完整的目录结构：

```sh
git clone https://github.com/BeautyyuYanli/abyss.git
```

加载 Abyss skill 后，在要开发的项目目录中打开 agent 会话，发送：

```text
use abyss workflow:proposal 设计一个文件共享服务，然后使用 workflow:impl 进行实现。
```

agent 会先执行设计流程，再把完成的方案交给实现流程。可以在同一条请求中补充技术栈、部署环境、功能范围等要求。

内置 workflow 会创建子会话，宿主需要提供会话创建、消息投递、并行执行和回收能力。Lody 的映射见 [Lody adapter](adapters/lody.md)。

## 内置 workflow

| Workflow | 用途 | 执行过程 |
| --- | --- | --- |
| `workflow:proposal` | 设计方案或修改已有方案。 | 起草、审查不必要的复杂性、落实简化、交付方案。 |
| `workflow:impl` | 按任务或已有方案实现。 | 实现后并行审查代码、正确性、测试质量、测试充分性和文档，汇总核实问题并返工，直到没有保留问题后交付报告。 |

`proposal` 将方案保存到工作区的 `.context/proposals/`。`impl` 在共享工作区中修改代码，最终报告保存到 `.context/impl/`，聚焦接口、数据模型、生命周期等对外可观察的变化。

## Workflow 示例

- [proposal.yaml](workflows/proposal.yaml)：起草方案，在独立会话中审查复杂性，再回到当前会话简化并交付。
- [impl.yaml](workflows/impl.yaml)：五路并行审查，汇总核实后决定返工或交付；返工复用原实现和审查会话。

## 更多调用示例

加载 Abyss 后，可以在对话中分别调用 workflow。

只设计方案：

```text
使用 workflow:proposal 设计一个文件共享服务，支持上传、生成分享链接和设置有效期，部署在单台服务器上。
```

修改已有方案：

```text
使用 workflow:proposal 修改刚才的方案，增加分享链接的下载次数限制。
```

按已有文档实现：

```text
使用 workflow:impl 按 docs/file-sharing.md 实现文件共享服务。
```

直接实现明确的任务：

```text
使用 workflow:impl 为当前项目的文件下载接口增加过期检查，并验证现有下载行为。
```

## 自定义 workflow

在 Abyss 安装目录的 `workflows/<name>.yaml` 中定义流程，然后通过 `workflow:<name>` 调用；也可以在请求中直接提供内联定义。定义语法和执行规则见 [SKILL.md](SKILL.md)。

## 许可证

[Apache License 2.0](LICENSE)。
