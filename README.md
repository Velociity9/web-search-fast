# Web Search MCP

基于 **Camoufox + FastAPI** 的高性能 Web 搜索服务，将搜索引擎结果转换为结构化 JSON / Markdown 输出。支持 MCP 协议（Streamable HTTP）供 LLM 客户端直接调用，同时提供 Admin 管理面板。

## 功能特性

- **三大搜索引擎**：Google、Bing、DuckDuckGo（自动回退）
- **多层深度抓取**：SERP 解析 → 正文提取 → 外链抓取
- **双格式输出**：JSON / Markdown
- **反检测浏览器**：Camoufox 真实浏览器指纹（GeoIP、Humanize、Locale）
- **自动扩容**：浏览器池并发达 80% 时自动扩容，上限可配
- **Admin 管理面板**：搜索统计、系统监控、API Key 管理、IP 封禁
- **API Key 认证**：Bearer Token 保护 MCP 端点和 Admin API

## 搜索深度

| depth | 行为 | 说明 |
|-------|------|------|
| `1` | SERP 解析 | 默认。提取标题、链接、摘要 |
| `2` | SERP + 正文 | 进入每个结果链接，提取页面正文 |
| `3` | SERP + 正文 + 外链 | 继续抓取正文中的外部链接内容 |

## 部署（Docker Compose）

### 1. 准备环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，设置关键参数：

```bash
# MCP 端点认证 Token（客户端调用时需携带）
MCP_AUTH_TOKEN=your-mcp-token-here

# Admin 面板认证 Token
ADMIN_TOKEN=your-admin-token-here

# 浏览器池配置
BROWSER_POOL_SIZE=5        # 初始 tab 数
BROWSER_MAX_POOL_SIZE=20   # 自动扩容上限
```

### 2. 构建并启动

```bash
docker compose up -d
```

首次构建需要编译 Nuitka 二进制，耗时较长。后续启动秒级完成。

### 3. 验证服务

```bash
# 健康检查
curl http://127.0.0.1:8897/health
# {"status":"ok","pool_ready":true}

# 查看容器状态
docker compose ps
```

服务就绪后：

| 地址 | 说明 |
|------|------|
| `http://127.0.0.1:8897/mcp` | MCP 端点（Streamable HTTP） |
| `http://127.0.0.1:8897/health` | 健康检查 |
| `http://127.0.0.1:8897/admin` | Admin 管理面板 |
| `http://127.0.0.1:8897/search` | REST API 搜索端点 |

### 4. 停止 / 更新

```bash
# 停止
docker compose down

# 更新代码后重新构建
docker compose up -d --build
```

## Admin 管理面板

访问 `http://127.0.0.1:8897/admin`，输入 `ADMIN_TOKEN` 登录。

面板功能：
- **Dashboard** — 搜索统计、CPU/内存监控、浏览器池状态、搜索延迟曲线、引擎分布、成功率
- **API Keys** — 创建/吊销 API Key，设置调用限额
- **IP Bans** — 封禁/解封 IP 地址
- **Search Logs** — 搜索历史记录，支持按 IP 过滤

### 通过 API 管理 Key

```bash
# 创建 API Key（返回 wsm_ 前缀的密钥，仅创建时可见）
curl -X POST http://127.0.0.1:8897/admin/api/keys \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "claude-code", "call_limit": 10000}'

# 列出所有 Key
curl http://127.0.0.1:8897/admin/api/keys \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 吊销 Key
curl -X DELETE http://127.0.0.1:8897/admin/api/keys/{key_id} \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## 添加到 Claude Code MCP

部署完成后，将服务注册为 Claude Code 的 MCP 工具。

### 方式一：使用脚本（推荐）

```bash
# 设置认证 Token（与 .env 中的 MCP_AUTH_TOKEN 一致）
export MCP_AUTH_TOKEN=your-mcp-token-here

# 注册到 Claude Code
./scripts/mcp-server.sh docker-register
```

### 方式二：手动注册

```bash
# 无认证
claude mcp add -s user -t http web-search-fast http://127.0.0.1:8897/mcp

# 有认证（推荐）
claude mcp add-json -s user web-search-fast '{
  "type": "http",
  "url": "http://127.0.0.1:8897/mcp",
  "headers": {"Authorization": "Bearer your-mcp-token-here"}
}'
```

### 方式三：使用 Admin 面板创建的 API Key

如果你通过 Admin 面板创建了 API Key（`wsm_` 前缀），也可以用它注册：

```bash
claude mcp add-json -s user web-search-fast '{
  "type": "http",
  "url": "http://127.0.0.1:8897/mcp",
  "headers": {"Authorization": "Bearer wsm_your-api-key-here"}
}'
```

注册后重启 Claude Code 会话即可使用 `web_search`、`get_page_content`、`list_search_engines` 三个工具。

### 认证优先级

服务按以下顺序验证 Bearer Token：

1. `MCP_AUTH_TOKEN` 环境变量（全局 Token）
2. `ADMIN_TOKEN` 环境变量（Admin Token）
3. 数据库中的 API Key（`wsm_` 前缀，通过 Admin 面板创建）

如果未配置任何认证（所有 Token 为空且无 DB Key），服务将允许无认证访问。

## MCP Tools

注册后 Claude Code 可使用以下工具：

| Tool | 说明 | 超时 |
|------|------|------|
| `web_search` | 搜索引擎查询，返回 Markdown | 25s |
| `get_page_content` | 获取单个 URL 页面内容 | 20s |
| `list_search_engines` | 列出可用引擎和浏览器池状态 | — |

## REST API

同时提供标准 HTTP API，可直接 curl 调用。

### GET /search

```bash
curl 'http://127.0.0.1:8897/search?q=python+asyncio&engine=duckduckgo&depth=1&max_results=5' \
  -H 'Authorization: Bearer your-token'
```

### POST /search

```bash
curl -X POST http://127.0.0.1:8897/search \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer your-token' \
  -d '{"query": "python asyncio", "engine": "duckduckgo", "depth": 2, "max_results": 5}'
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `q` / `query` | string | 必填 | 搜索关键词（1-500 字符） |
| `engine` | string | `google` | `google` / `bing` / `duckduckgo` |
| `depth` | int | `1` | 抓取深度：1-3 |
| `format` | string | `json` | `json` / `markdown` |
| `max_results` | int | `10` | 最大结果数（1-50） |
| `timeout` | int | `30` | 超时秒数（5-120） |

## 引擎状态

| 引擎 | 状态 | 说明 |
|------|------|------|
| **DuckDuckGo** | 稳定可用 | 推荐默认，HTML-lite 模式 |
| **Google** | 受限 | 部分 IP 触发验证码，自动回退 |
| **Bing** | 可用 | `global.bing.com` 避免地域重定向 |

> Google 被拦截时自动按 DuckDuckGo → Bing 顺序回退。

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MCP_AUTH_TOKEN` | 空 | MCP 端点认证 Token |
| `ADMIN_TOKEN` | 空 | Admin 面板认证 Token |
| `BROWSER_POOL_SIZE` | `5` | 初始浏览器 tab 数 |
| `BROWSER_MAX_POOL_SIZE` | `20` | 自动扩容上限 |
| `BROWSER_PROXY` | 空 | 代理服务器（socks5/http） |
| `BROWSER_OS` | 空 | 目标 OS 指纹（windows/macos/linux） |
| `BROWSER_FONTS` | 空 | 自定义字体列表 |
| `BROWSER_BLOCK_WEBGL` | `false` | 阻止 WebGL 指纹 |
| `BROWSER_ADDONS` | 空 | Firefox 插件路径 |
| `MCP_PORT` | `8897` | 服务端口 |
| `WSM_DB_PATH` | `wsm.db` | SQLite 数据库路径 |
| `REDIS_URL` | 空 | Redis 连接地址（可选） |

## 本地开发

```bash
# 安装依赖
pip install -e ".[dev]"

# 安装 Camoufox 浏览器
python -m camoufox fetch

# 启动服务
python -m src.mcp_server --transport http --host 127.0.0.1 --port 8897

# 运行测试（99 个）
pytest tests/ -v

# 类型检查
mypy src/

# 代码格式化
ruff check src/ --fix && ruff format src/
```

## 项目结构

```
web-search-mcp/
├── src/
│   ├── main.py                 # FastAPI 入口
│   ├── mcp_server.py           # MCP 服务入口（FastMCP + 中间件 + Admin）
│   ├── config.py               # 配置管理
│   ├── api/
│   │   ├── routes.py           # HTTP API 路由
│   │   └── schemas.py          # Pydantic 请求/响应模型
│   ├── core/
│   │   └── search.py           # 搜索逻辑（MCP + HTTP 共用）
│   ├── engine/
│   │   ├── base.py             # 搜索引擎抽象基类
│   │   ├── google.py           # Google（JS DOM + 验证码检测）
│   │   ├── bing.py             # Bing（global.bing.com）
│   │   └── duckduckgo.py       # DuckDuckGo（HTML-lite）
│   ├── scraper/
│   │   ├── browser.py          # BrowserPool（自动扩容 + 健康监控）
│   │   ├── parser.py           # HTML 内容解析
│   │   └── depth.py            # 多层深度抓取
│   ├── formatter/
│   │   ├── json_fmt.py         # JSON 格式化
│   │   └── markdown_fmt.py     # Markdown 格式化
│   ├── admin/
│   │   ├── database.py         # SQLite 初始化 + 迁移
│   │   ├── repository.py       # 数据访问层
│   │   ├── routes.py           # Admin REST API
│   │   └── static/             # Admin SPA 构建产物
│   └── middleware/
│       ├── api_key_auth.py     # Bearer Token 认证
│       ├── ip_ban.py           # IP 封禁
│       └── search_log.py       # 搜索日志
├── admin-ui/                   # Admin 前端（React + Vite + Tailwind）
├── tests/                      # 测试（99 个）
├── scripts/
│   └── mcp-server.sh           # MCP 注册管理脚本
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI + Uvicorn + Starlette |
| MCP 框架 | FastMCP (mcp>=1.25.0) |
| 浏览器引擎 | Camoufox（反检测 Firefox，Playwright 驱动） |
| 异步运行时 | asyncio + Semaphore 并发控制 |
| HTML 解析 | BeautifulSoup4 + lxml |
| 内容转换 | markdownify（HTML → Markdown） |
| 数据库 | SQLite (aiosqlite) |
| 缓存 | Redis（可选） |
| Admin 前端 | React + Vite + Tailwind CSS + recharts |
| 数据校验 | Pydantic v2 |

## License

MIT
