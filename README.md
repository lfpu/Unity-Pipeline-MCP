# Unity-Pipeline-MCP

一个 stdio MCP 服务，通过 Unity 官方 `com.unity.pipeline` 包在 Editor 里启动的本地 HTTP API 来操作正在运行的 Unity Editor。

## 工具

| 工具 | 说明 |
|---|---|
| `unity_status` | 只读。Editor 是否在运行、项目名、Unity 版本、端口、心跳、命令数量、警告。不返回 token |
| `unity_commands` | 只读。检索可用命令。无参数列出分组；`group` / `keyword` 过滤；`command` 返回完整参数 schema |
| `unity_exec` | 执行一个命令。支持 dry-run 的写操作必须先用 `dryRun=true` 试运行一次 |

## 运行前提

- Unity 6.0 及以上，项目里已安装 Unity Pipeline 包（`unity pipeline install`），Editor 已打开该项目。
- Python 3.10+，`pip install -r requirements.txt`。

## 配置（AntCode / Claude Code 等）

参考 `.mcp.json.example`：

```json
{
  "mcpServers": {
    "unity-pipeline": {
      "command": "python",
      "args": ["C:/path/to/Unity-Pipeline-MCP/main.py", "--project", "C:/path/to/YourUnityProject"]
    }
  }
}
```

## 启动参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--project <路径>` | 必填 | Unity 项目根目录，用来定位 `Library/Pipeline/.unity-pipeline-port` |
| `--allow-eval` / `--no-allow-eval` | 关 | 是否开放 Eval 类命令（能执行任意 C#，默认禁用） |
| `--require-dry-run` / `--no-require-dry-run` | 开 | 写操作是否必须先 dry-run |
| `--timeout-ms` | 60000 | 默认执行超时 |
| `--max-chars` | 8000 | 单次返回给模型的最大字符数 |
| `--deny <通配符>` | 空 | 禁用的命令名，可重复或用逗号分隔 |
| `--readonly-pattern <通配符>` | 空 | 视为只读的命令名，不要求 dry-run |

对应环境变量：`UNITY_MCP_PROJECT`、`UNITY_MCP_ALLOW_EVAL`、`UNITY_MCP_REQUIRE_DRY_RUN`、`UNITY_MCP_TIMEOUT_MS`、`UNITY_MCP_MAX_CHARS`、`UNITY_MCP_DENY`、`UNITY_MCP_READONLY`。

## 工作方式

- 每次调用都重新读取 `Library/Pipeline/.unity-pipeline-port`，取端口和 token，不缓存 token，也不写日志、不返回给模型。
- 先检查端口文件里的 `pid` 进程是否存活，避免用旧的端口文件。
- 请求头 `Authorization: Bearer <evalToken>`，只连 `127.0.0.1`，不带 `Origin` 头，不走代理。
- 收到 401 时重新读文件并重试一次（Editor 重启后 token 会变）。
- `unity_exec` 同一时刻只发一个请求（服务端本来就串行执行）。
- 命令列表缓存 60 秒，Editor 重启后自动失效。

## 错误码

所有错误返回 `{ok:false, code, message, hint}`。

`project_not_set`、`port_file_missing`、`port_file_unreadable`、`editor_not_running`、`server_unreachable`、`auth_failed`、`command_not_found`、`invalid_parameters`、`dry_run_required`、`dry_run_unsupported`、`blocked_by_policy`、`command_failed`、`timeout`、`payload_too_large`、`server_error`、`internal_error`。

## 尚未用真实 Unity 验证的地方

- `/api/exec` 的响应体结构没有核实，第一版原样透传，只把 `success:false` / `ok:false` / `error` 字段当作失败。
- 端口文件里 token 字段名取自实测输出（`evalToken`）。
- Eval 命令的真实名称没有核实，目前按命令名或 tags 里含 `eval` 一词判断。
- 只读/写入的区分没有可靠依据，需要用 `--readonly-pattern` 手工配置。
- 请求里的 `job` 字段只在较新版本文档里出现，本服务没有使用。

## 安全提醒

端口文件里的 token 能触发 Eval，等同于本机代码执行权限。不要把它写进配置、日志或对话。
