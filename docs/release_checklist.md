# CloudMem Release Checklist

## 1) 关键命令 Smoke
- `cloudmem --help`
- `cloudmem status`
- `cloudmem onboard --help`
- `python -m cloudmem.mcp_server`（可启动并响应 `initialize` / `tools/list`）

## 2) 失败路径验证（必测）
- MCP 读工具在 collection/metadata 读取失败时返回结构化错误：
  - `mempalace_status`
  - `mempalace_list_wings`
  - `mempalace_list_rooms`
  - `mempalace_get_taxonomy`
- 确认不是“空 wings/rooms/taxonomy”假成功。

## 3) Sync 与 Hook 验证
- `cloudmem sync-status`
- `cloudmem push` / `cloudmem pull` 基本链路可用
- `hooks/post-session.sh` 能调用 `cloudmem session-finalize`
- `mempal_save_hook.sh` / `mempal_precompact_hook.sh`：
  - 优先写 `~/.cloudmem/hook_state`
  - 可兼容读取旧 `~/.mempalace/hook_state`

## 4) MCP 健康检查
- `tools/list` 返回非空工具集
- `tools/call` 成功路径返回 JSON 文本 payload
- `tools/call` 失败路径（读异常）返回结构化 `error.code` + `detail` + `palace_path`

## 5) 测试建议
- 先跑变更相关：
  - `pytest tests/test_mcp_server_errors.py tests/test_mcp_server_tools.py tests/test_onboarding_cli.py -q`
- 再跑全量：
  - `pytest tests/ -v`
