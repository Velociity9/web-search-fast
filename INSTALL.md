# 安装 Web Search MCP 到 Claude Code

## 前置条件

- Claude Code CLI 已安装（`claude` 命令可用）
- Python 3.10+ 或 Docker

---

## 方式一：本地 stdio 模式（推荐）

最简单的方式，Claude Code 直接通过 stdin/stdout 与 MCP 通信，无需启动后台服务。

```bash
# 1. 克隆项目
git clone https://github.com/nicepkg/web-search-mcp.git
cd web-search-mcp

# 2. 安装依赖
pip install -e .

# 3. 安装 Camoufox 浏览器
python -m camoufox fetch

# 4. 注册到 Claude Code（一键命令）
claude mcp add-json -s user web-search-fast '{
  "type": "stdio",
  "command": "python",
  "args": ["-m", "src.mcp_server", "--transport", "stdio"],
  "env": {"PYTHONUNBUFFERED": "1"},
  "cwd": "'$(pwd)'"
}'

# 5. 验证注册
claude mcp get web-search-fast

# 6. 重启 Claude Code 会话生效
```

> 如果你的 Python 不在 PATH 中，把 `"command": "python"` 替换为完整路径，例如 `"/usr/bin/python3"`。

---

## 方式二：Docker HTTP 模式

适合服务器部署或需要持久运行的场景。

```bash
# 1. 克隆项目
git clone https://github.com/nicepkg/web-search-mcp.git
cd web-search-mcp

# 2. 启动 Docker 服务
docker compose up -d

# 3. 等待服务就绪（健康检查）
curl -s http://127.0.0.1:8897/health
# 返回 {"status":"ok"} 表示就绪

# 4. 注册到 Claude Code（无认证）
claude mcp add -s user -t http web-search-fast http://127.0.0.1:8897/mcp

# 5. 验证注册
claude mcp get web-search-fast

# 6. 重启 Claude Code 会话生效
```

### Docker + API Key 认证

```bash
# 启动时设置认证 Token
MCP_AUTH_TOKEN="your-secret-key" docker compose up -d

# 注册（带 Bearer Token）
claude mcp add-json -s user web-search-fast '{
  "type": "http",
  "url": "http://127.0.0.1:8897/mcp",
  "headers": {"Authorization": "Bearer your-secret-key"}
}'
```

### Docker 自定义端口

```bash
MCP_PORT=9000 docker compose up -d

claude mcp add -s user -t http web-search-fast http://127.0.0.1:9000/mcp
```

---

## 方式三：使用项目脚本

项目自带管理脚本 `scripts/mcp-server.sh`，封装了注册/启停操作。

> 使用前需编辑脚本第 13 行的 `PYTHON` 变量，改为你的 Python 路径。

```bash
# 注册 stdio 模式
./scripts/mcp-server.sh register

# 注册 Docker HTTP 模式
./scripts/mcp-server.sh docker-register

# 带认证的 Docker 注册
MCP_AUTH_TOKEN="your-key" ./scripts/mcp-server.sh docker-register

# 查看状态
./scripts/mcp-server.sh status

# 更新注册（删除旧的 + 重新注册）
./scripts/mcp-server.sh update           # stdio
./scripts/mcp-server.sh docker-update    # docker

# 卸载
./scripts/mcp-server.sh unregister
```

---

## 验证安装

注册完成并重启 Claude Code 后，在对话中测试：

```
搜索一下 Python 3.13 的新特性
```

Claude Code 应该会调用 `web_search` 工具并返回实时搜索结果。

也可以用 curl 直接测试 MCP 端点（仅 HTTP 模式）：

```bash
# 初始化会话
curl -s -X POST http://127.0.0.1:8897/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | jq .

# 搜索测试
curl -s -X POST http://127.0.0.1:8897/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"web_search","arguments":{"query":"hello world","engine":"duckduckgo","max_results":3}}}' | jq .
```

---

## 卸载

```bash
# 从 Claude Code 移除
claude mcp remove web-search-fast -s user

# 停止 Docker（如果使用 Docker 模式）
docker compose down
```

---

## 可用 MCP 工具

| 工具 | 说明 | 超时 |
|------|------|------|
| `web_search` | 搜索引擎查询，返回标题/链接/摘要 | 25s |
| `get_page_content` | 获取单个 URL 的页面正文 | 20s |
| `list_search_engines` | 列出可用搜索引擎和浏览器池状态 | — |

### web_search 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | string | 必填 | 搜索关键词 |
| `engine` | string | `duckduckgo` | `google` / `bing` / `duckduckgo` |
| `depth` | int | `1` | 1=SERP, 2=SERP+正文 |
| `max_results` | int | `5` | 最大结果数 (1-20) |

### get_page_content 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `url` | string | 要获取内容的 URL |

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `MCP_AUTH_TOKEN` | API 认证 Token | 空（无认证） |
| `BROWSER_POOL_SIZE` | 浏览器并发数 | `3` |
| `BROWSER_PROXY` | 代理服务器 | — |
| `BROWSER_OS` | 目标 OS 指纹 | — |
| `BROWSER_BLOCK_WEBGL` | 阻止 WebGL | `false` |
| `ADMIN_TOKEN` | Admin 面板密码 | — |
