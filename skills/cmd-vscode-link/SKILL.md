---
name: cmd-vscode-link
description: 为当前工作目录或指定目录生成 VS Code Remote SSH deeplink，使用本机 192.168.* 局域网地址，以聊天界面可点击的 Markdown HTTPS 跳转链接返回。适用于用户索要 VS Code 连接本机、打开当前项目的链接，或调用 cmd-vscode-link。
---

# VS Code 局域网链接

把用户指定的目录（默认当前工作目录）转换为 VS Code Remote SSH 链接。
默认使用当前机器的 `192.168.*` 局域网 IPv4 地址；用户明确指定的地址、
SSH 用户、端口和目录优先。不复用旧会话中的 IP 或硬编码某个项目路径。

## 确认连接信息

- 获取目标目录的绝对路径，默认通过 `pwd` 获取当前工作目录。
- 默认通过 `id -un` 获取当前用户名。
- 在 Linux 上读取 `ip -4 -o addr show scope global` 和
  `ip -4 route show default`，选择实际连接局域网的网卡地址。
  优先使用默认路由对应的有线或 Wi-Fi 网卡上的 `192.168.*` 地址，
  排除 Docker/容器网桥、回环和 VPN 地址，不能直接取第一条 `192.*`。
  其他系统使用其本机网络查询工具获取同类信息。
- 找不到符合要求的地址时说明结果，不编造地址或擅自改用公网、容器地址。
  多个地址且无法根据路由判断时，给出带网卡说明的候选链接。
- SSH 默认端口为 `22`。可用 `ss -ltn 'sport = :22'` 检查监听；
  指定其他端口时相应替换。监听状态不能证明另一台设备已能连接或认证。
  若未监听，仍可生成链接，但简短说明需要先启动对应 SSH 服务。

## 构造可点击链接

底层 URI 格式：

```text
vscode://vscode-remote/ssh-remote+USER@LAN_IP/absolute/project/path
```

非默认端口使用 `USER@LAN_IP:PORT`。使用标准 URL 编码库，例如 Python
`urllib.parse.quote`：用户名以 `safe=""` 编码，绝对路径以 `safe="/"` 编码。
保留 URI 中结构性的 `ssh-remote+`、`@` 和端口分隔符。

聊天界面可能不渲染 `vscode://` 链接。默认将完整底层 URI 再以
`quote(uri, safe="")` 编码一次，作为以下 HTTPS 链接的 `url` 查询参数：

```text
https://vscode.dev/redirect?url=ENCODED_URI
```

不要直接把底层 URI 拼入查询参数：未编码的 `+` 可能被解析成空格。
路径里的空格、中文、`#`、`?` 和 `%` 也必须经过正确的内外两层编码。

## 回复格式

默认只返回一个真正的 Markdown 链接，链接文字使用目标目录或项目名：

```markdown
[用 VS Code 打开 项目名](https://vscode.dev/redirect?url=ENCODED_URI)
```

实际回复中替换所有占位内容，不用代码块或反引号包住链接。
用户明确要求原始 URI 或 Markdown 源码时，再提供对应的可复制文本。
若用户反馈“没有链接”，使用上述 HTTPS 跳转格式，不重复被隐藏的自定义协议链接。
仅在有实际连接前提未满足时补充一句说明，例如客户端需要安装 Remote - SSH。
