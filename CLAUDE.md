# Web Search MCP

## 项目概述

基于 **Camoufox + FastAPI** 的高性能 Web 搜索服务，将搜索引擎结果转换为结构化 JSON / Markdown 输出。支持多层深度抓取与并发执行。

## 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| Web 框架 | FastAPI + Uvicorn | HTTP API 服务 |
| 浏览器引擎 | Camoufox (Playwright) | 反检测浏览器抓取 |
| 异步运行时 | asyncio | 并发调度 |
| HTML 解析 | BeautifulSoup4 / lxml | 页面内容提取 |
| 内容转换 | markdownify | HTML → Markdown |

## 核心功能

### 搜索引擎支持

- **Google**（默认）
- **Bing**
- **DuckDuckGo**

### 搜索深度（depth）

| 层级 | 行为 | 说明 |
|------|------|------|
| `depth=1` | SERP 解析 | 默认。提取搜索结果页的标题、链接、摘要 |
| `depth=2` | SERP + 正文抓取 | 进入每个结果链接，提取页面正文内容 |
| `depth=3` | SERP + 正文 + 外链抓取 | 继续抓取正文中的外部链接内容 |

### 返回格式

- `format=json` — 结构化 JSON
- `format=markdown` — Markdown 文档

## 项目结构

```
web-search-mcp/
├── CLAUDE.md
├── pyproject.toml
├── README.md
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置管理
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py           # API 路由定义
│   │   └── schemas.py          # Pydantic 请求/响应模型
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── base.py             # 搜索引擎抽象基类
│   │   ├── google.py           # Google 搜索实现
│   │   ├── bing.py             # Bing 搜索实现
│   │   └── duckduckgo.py       # DuckDuckGo 搜索实现
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── browser.py          # Camoufox 浏览器池管理
│   │   ├── parser.py           # HTML 内容解析与提取
│   │   └── depth.py            # 多层深度抓取调度
│   └── formatter/
│       ├── __init__.py
│       ├── json_fmt.py         # JSON 格式化输出
│       └── markdown_fmt.py     # Markdown 格式化输出
├── tests/
│   ├── __init__.py
│   ├── test_api.py             # API 接口测试
│   ├── test_engine.py          # 搜索引擎测试
│   ├── test_scraper.py         # 抓取器测试
│   └── test_formatter.py       # 格式化输出测试
└── docs/
    ├── CHANGELOG.md
    └── tasks/
```

## API 设计

### `POST /search`

```json
{
  "query": "搜索关键词",
  "engine": "google",
  "depth": 1,
  "format": "json",
  "max_results": 10,
  "timeout": 30
}
```

### `GET /search`

```
GET /search?q=关键词&engine=google&depth=1&format=json&max_results=10
```

### 响应结构（JSON）

```json
{
  "query": "搜索关键词",
  "engine": "google",
  "depth": 1,
  "total": 10,
  "results": [
    {
      "title": "页面标题",
      "url": "https://example.com",
      "snippet": "搜索摘要...",
      "content": "正文内容（depth>=2 时返回）",
      "sub_links": [
        {
          "url": "https://...",
          "content": "外链内容（depth=3 时返回）"
        }
      ]
    }
  ],
  "metadata": {
    "elapsed_ms": 1234,
    "timestamp": "2026-02-11T00:00:00Z"
  }
}
```

## 并发策略

- **浏览器池**：预启动 N 个 Camoufox 实例，通过 asyncio.Semaphore 控制并发
- **页面级并发**：depth>=2 时，多个结果页面并行抓取
- **引擎级并发**：支持同时查询多个搜索引擎并合并结果

## 开发规范

### 命令

```bash
# 安装依赖
pip install -e ".[dev]"

# 启动开发服务
uvicorn src.main:app --reload --port 8000

# 运行测试
pytest tests/ -v

# 类型检查
mypy src/

# 代码格式化
ruff check src/ --fix
ruff format src/
```

### 代码风格

- Python 3.11+
- 异步优先：所有 I/O 操作使用 async/await
- 类型注解：所有公开函数必须有类型注解
- Pydantic v2 用于数据校验
- 遵循 PEP 8，使用 ruff 格式化

### 测试要求

- 每个功能模块必须有对应的测试文件
- 使用 pytest + pytest-asyncio
- 关键路径需要集成测试

### Git 规范

- Commit message 使用 Conventional Commits 格式
- 不包含 AI 辅助相关字样
- 不包含 anthropic 相关字样

### 文档管理

- 变更日志：`docs/CHANGELOG.md`
- 任务记录：`docs/tasks/【任务名】.md`
- `docs/` 目录在 `.gitignore` 中忽略
