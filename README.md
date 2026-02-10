# Web Search MCP

基于 **Camoufox + FastAPI** 的高性能 Web 搜索服务，将搜索引擎结果转换为结构化 JSON / Markdown 输出。支持多层深度抓取与并发执行。

## 功能特性

- **三大搜索引擎**：Google、Bing、DuckDuckGo
- **多层深度抓取**：SERP 解析 → 正文提取 → 外链抓取
- **双格式输出**：JSON / Markdown
- **反检测浏览器**：Camoufox 真实浏览器指纹（geoip、humanize、locale）
- **并发执行**：浏览器池 + asyncio 信号量控制
- **引擎自动回退**：主引擎无结果时自动切换备选引擎

## 搜索深度

| depth | 行为 | 说明 |
|-------|------|------|
| `1` | SERP 解析 | 默认。提取标题、链接、摘要 |
| `2` | SERP + 正文 | 进入每个结果链接，提取页面正文 |
| `3` | SERP + 正文 + 外链 | 继续抓取正文中的外部链接内容 |

## 快速开始

### 安装

```bash
# 克隆项目
git clone <repo-url> && cd web-search-mcp

# 安装依赖
pip install -e ".[dev]"

# 安装 Camoufox 浏览器
python -m camoufox fetch
```

### 启动服务

```bash
# 开发模式（自动重载）
uvicorn src.main:app --reload --port 8000

# 生产模式
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

服务启动后访问 `http://localhost:8000/health` 确认状态：

```bash
curl http://localhost:8000/health
# {"status":"ok","pool_ready":true}
```

## API 使用

### GET /search

```bash
# 基础搜索（默认 Google，depth=1，JSON 格式）
curl 'http://localhost:8000/search?q=python+asyncio'

# 指定引擎 + 深度
curl 'http://localhost:8000/search?q=firsh.me+blog&engine=duckduckgo&depth=2&max_results=3'

# Markdown 格式输出
curl 'http://localhost:8000/search?q=firsh.me+blog&engine=duckduckgo&format=markdown'

# Bing 搜索
curl 'http://localhost:8000/search?q=fastapi+tutorial&engine=bing&max_results=5'

# 三层深度抓取（SERP + 正文 + 外链）
curl 'http://localhost:8000/search?q=web+scraping&engine=duckduckgo&depth=3&max_results=3'
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `q` | string | 必填 | 搜索关键词（1-500 字符） |
| `engine` | string | `google` | 搜索引擎：`google` / `bing` / `duckduckgo` |
| `depth` | int | `1` | 抓取深度：1-3 |
| `format` | string | `json` | 输出格式：`json` / `markdown` |
| `max_results` | int | `10` | 最大结果数（1-50） |
| `timeout` | int | `30` | 超时秒数（5-120） |

### POST /search

```bash
curl -X POST http://localhost:8000/search \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "firsh.me blog",
    "engine": "duckduckgo",
    "depth": 2,
    "format": "json",
    "max_results": 5,
    "timeout": 30
  }'
```

### 响应示例

**JSON 格式（depth=1）：**

```json
{
  "query": "firsh.me blog",
  "engine": "duckduckgo",
  "depth": 1,
  "total": 3,
  "results": [
    {
      "title": "NeoJ's Web Page [下水鱼的Blog]",
      "url": "https://firsh.me/",
      "snippet": "这是一个关于下水鱼的个人网站的博客页面。",
      "content": "",
      "sub_links": []
    }
  ],
  "metadata": {
    "elapsed_ms": 2824,
    "timestamp": "2026-02-10T17:02:20.891421+00:00",
    "engine": "duckduckgo",
    "depth": 1
  }
}
```

**JSON 格式（depth=2，包含正文内容）：**

```json
{
  "query": "firsh.me blog",
  "engine": "duckduckgo",
  "depth": 2,
  "total": 3,
  "results": [
    {
      "title": "NeoJ's Web Page [下水鱼的Blog]",
      "url": "https://firsh.me/",
      "snippet": "这是一个关于下水鱼的个人网站的博客页面。",
      "content": "blog/2026\n2026-02-02\n关闭Chrome 自动更新...",
      "sub_links": []
    }
  ],
  "metadata": {
    "elapsed_ms": 5224,
    "timestamp": "2026-02-10T17:06:36.644148+00:00",
    "engine": "duckduckgo",
    "depth": 2
  }
}
```

**Markdown 格式：**

```markdown
# Search Results: firsh.me blog

**Engine:** duckduckgo | **Depth:** 1 | **Results:** 3
**Time:** 1792ms

---

## 1. NeoJ's Web Page [下水鱼的Blog]
**URL:** https://firsh.me/

> 这是一个关于下水鱼的个人网站的博客页面。
```

## 引擎状态

| 引擎 | 状态 | 说明 |
|------|------|------|
| **DuckDuckGo** | 稳定可用 | 推荐使用，搜索质量高，无地域限制 |
| **Google** | 受限 | 部分 IP 会触发验证码，自动回退到 DuckDuckGo |
| **Bing** | 可用 | 使用 `global.bing.com` 避免地域重定向，部分 IP 结果相关性较低 |

> Google 被拦截时会自动按 DuckDuckGo → Bing 顺序回退，响应中的 `engine` 字段标识实际使用的引擎。

## 测试

```bash
# 单元测试（26 个测试）
pytest tests/ -v

# 集成测试（自动启动服务，真实搜索）
python scripts/test_live.py

# 集成测试 - 自定义参数
python scripts/test_live.py --query "python asyncio" --engines duckduckgo --max-depth 2

# 集成测试 - 服务已在运行时
python scripts/test_live.py --no-server --engines duckduckgo google --max-depth 3
```

## 项目结构

```
web-search-mcp/
├── src/
│   ├── main.py                 # FastAPI 入口 + 浏览器池生命周期
│   ├── config.py               # 配置管理（BrowserConfig / AppConfig）
│   ├── api/
│   │   ├── routes.py           # API 路由 + 引擎回退逻辑
│   │   └── schemas.py          # Pydantic 请求/响应模型
│   ├── engine/
│   │   ├── base.py             # 搜索引擎抽象基类
│   │   ├── google.py           # Google（含首页预热 + 验证码检测）
│   │   ├── bing.py             # Bing（global.bing.com + URL 解码）
│   │   └── duckduckgo.py       # DuckDuckGo
│   ├── scraper/
│   │   ├── browser.py          # Camoufox 浏览器池
│   │   ├── parser.py           # HTML 内容解析
│   │   └── depth.py            # 多层深度抓取调度
│   └── formatter/
│       ├── json_fmt.py         # JSON 格式化
│       └── markdown_fmt.py     # Markdown 格式化
├── tests/                      # 单元测试
├── scripts/
│   └── test_live.py            # 集成测试脚本
└── pyproject.toml
```

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI + Uvicorn |
| 浏览器引擎 | Camoufox（反检测 Firefox，Playwright 驱动） |
| 异步运行时 | asyncio + Semaphore 并发控制 |
| HTML 解析 | BeautifulSoup4 + lxml |
| 内容转换 | markdownify（HTML → Markdown） |
| 数据校验 | Pydantic v2 |

## License

MIT
