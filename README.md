# legado-web · Docker 移植版

将安卓阅读 App [legado](https://github.com/warpdotsys/legado) 移植到 Docker 平台。
原生 Web 界面 + 完整兼容 legado 的 HTTP/WebSocket API，无需安卓模拟器即可在任意服务器上运行。

> **端口保留**：保留 legado 原生 Web 服务端口 —— HTTP `1122`（API + Web UI）与 WebSocket `1123`（搜索 / 书源调试 / 订阅源调试）。

---

## 特性

- **原生 Web 界面**：书架、搜索、阅读器、书源 / 订阅源 / 替换规则管理，响应式布局，移动端友好。
- **API 全兼容**：复刻 legado 的 `BookController` / `BookSourceController` / `RssSourceController` / `ReplaceRuleController`，返回体 `{isSuccess, errorMsg, data}` 与原版一致。
- **书源引擎**：解析 legado 书源 JSON 规则（搜索 / 详情 / 目录 / 正文 / 正则净化），支持 `bs4` + `lxml` 加速解析。
- **WebSocket**：`/searchBook`、`/bookSourceDebug`、`/rssSourceDebug` 实时推送。
- **数据持久化**：SQLite（与 legado 数据库 schema 对齐），数据卷挂载即可备份迁移。

---

## 快速开始

### Docker（推荐）

```bash
docker compose up -d --build
# 打开 http://localhost:1122
```

停止 / 查看日志：

```bash
docker compose logs -f legado-web
docker compose down
```

数据持久化在 `legado-data` 卷中，`down` 不会删除数据。

### 单独 docker run

```bash
docker build -t legado-web .
docker run -d --name legado-web \
  -p 1122:1122 -p 1123:1123 \
  -v legado-data:/data \
  --restart unless-stopped \
  legado-web
```

### 本地运行（无需 Docker）

```bash
pip install -r backend/requirements.txt   # 可选；标准库即可运行
python3 backend/server.py
```

---

## 配置（环境变量）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LEGADO_WEB_PORT` | `1122` | HTTP 服务端口；WebSocket 端口自动为 `WEB_PORT + 1`（即 `1123`） |
| `LEGADO_DB` | `/data/legado.db` | SQLite 数据库路径 |
| `LEGADO_FRONTEND_DIR` | `<repo>/frontend` | 静态前端目录 |

---

## 端口

| 端口 | 协议 | 用途 |
| --- | --- | --- |
| `1122` | HTTP | Web UI + 全部 JSON API |
| `1123` | WebSocket | 实时搜索 / 书源调试 / 订阅源调试 |

---

## HTTP API（与 legado 兼容）

所有响应均为 `{"isSuccess": bool, "errorMsg": str, "data": ...}`。

### 书架 / 书籍（BookController）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/getBookshelf` | 获取书架 |
| GET | `/getChapterList?url=` | 获取目录 |
| GET | `/refreshToc?url=` | 刷新目录 |
| GET | `/getBookContent?url=&index=` | 获取章节正文 |
| POST | `/saveBook` | 保存书籍（body: Book JSON） |
| POST | `/deleteBook` | 删除书籍 |
| POST | `/saveBookProgress` | 保存阅读进度 |
| GET | `/cover?url=` | 书籍封面 |
| GET | `/image?url=` | 正文图片 |
| GET | `/getReadConfig` | 获取阅读配置 |
| POST | `/saveReadConfig` | 保存阅读配置 |

### 书源（BookSourceController）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/getBookSources` | 获取全部书源 |
| GET | `/getBookSource?url=` | 获取单个书源 |
| POST | `/saveBookSource` | 保存单个书源 |
| POST | `/saveBookSources` | 批量保存书源 |
| POST | `/deleteBookSources` | 删除书源（body: 书源数组） |

### 订阅源（RssSourceController）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/getRssSources` | 获取全部订阅源 |
| GET | `/getRssSource?url=` | 获取单个订阅源 |
| POST | `/saveRssSource` | 保存订阅源 |
| POST | `/saveRssSources` | 批量保存订阅源 |
| POST | `/deleteRssSources` | 删除订阅源（body: 订阅源数组） |

### 替换规则（ReplaceRuleController）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/getReplaceRules` | 获取全部替换规则 |
| POST | `/saveReplaceRule` | 保存规则 |
| POST | `/deleteReplaceRule` | 删除规则 |
| POST | `/testReplaceRule` | 测试规则 |

### WebSocket（端口 1123）

| 路径 | 说明 |
| --- | --- |
| `/searchBook` | 实时搜索推送 |
| `/bookSourceDebug` | 书源调试输出 |
| `/rssSourceDebug` | 订阅源调试输出 |

---

## 数据备份 / 迁移

```bash
# 备份
docker run --rm -v legado-data:/data -v "$PWD":/bk alpine \
  cp /data/legado.db /bk/legado.db.bak

# 恢复
docker run --rm -v legado-data:/data -v "$PWD":/bk alpine \
  cp /bk/legado.db.bak /data/legado.db
```

---

## 项目结构

```
.
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── backend/
│   ├── server.py          # HTTP :1122 + WebSocket :1123 入口
│   ├── api.py             # Controller（ReturnData / Book / BookSource / Rss / ReplaceRule）
│   ├── database.py        # SQLite DAO（schema 对齐 legado entities）
│   ├── models.py          # 数据模型（Book / BookSource / RssSource / ReplaceRule / BookChapter）
│   ├── book_engine.py     # 书源规则执行（搜索 / 详情 / 目录 / 正文）
│   ├── rule_engine.py     # 正则净化 + bs4/lxml 解析
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── css/               # app / bookshelf / reader / search / source
    └── js/
        ├── app.js  router.js  store.js  api.js  ui.js
        └── views/  bookshelf search reader bookSource rssSource replaceRule about
```

## 与原版 legado 的关系

本移植 **不包含** 安卓 UI、TTS、本地 epub/txt 导入等设备相关功能，专注于把 legado 的 **Web 服务层** 与 **书源引擎** 迁移到服务端，使其可在 Docker / 服务器上长期运行并通过浏览器访问。书源规则格式与 legado 完全一致，可直接导入既有书源 JSON。
