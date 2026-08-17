# Skinflow

Skinflow 是一个面向 Windows 的本地 CS2 半自动交易工作台，用于扫描公开行情、同步 Steam 库存、创建挂单预览、跟踪挂单对账，并维护本地 FIFO 持仓账本。

Skinflow is a Windows-first, local CS2 semi-automatic trading workspace. It helps one operator scan public market data, synchronize Steam inventory, build listing previews, track listing reconciliation, and maintain a local FIFO holdings ledger.

Skinflow 是操作辅助工具，不是自动交易机器人。挂单必须由用户明确确认，Steam 手机确认也始终由用户手动完成。

Skinflow is an operator tool, not an automated trading bot. Listing submission always requires an explicit user action, and Steam mobile confirmations remain manual.

## 功能 / Capabilities

| 模块 / Area | 功能 / What it does | 是否需要 Steam 会话 / Steam session required |
| --- | --- | --- |
| 扫描 / Scan | 汇集 BUFF、Steam、CSQAQ、悠悠等公开行情，提供筛选和实时进度。<br>Collects public BUFF, Steam, CSQAQ, and Youpin market data; applies filters and streams progress. | 否 / No |
| 库存 / Inventory | 同步 Steam 单件资产、可交易状态与库存分组。<br>Synchronizes individual Steam assets, trade availability, and grouped inventory. | 是 / Yes |
| 挂单 / Listings | 创建预览、后台逐件提交、对账 active/pending/cancelled 状态，并支持批量取消。<br>Creates previews, submits selected items in the background, reconciles active/pending/cancelled states, and supports batch cancellation. | 是 / Yes |
| 持仓 / Holdings | 使用 FIFO 记录买入卖出，并维护未售持仓。<br>Records purchases and sales with FIFO accounting, plus local maintenance of open holdings. | 否 / No |
| 桌面壳 / Desktop shell | 托管本地 API 与 WebView2，执行本地启动鉴权并记住窗口大小。<br>Hosts the local API and WebView2 interface, handles local startup authentication, and remembers window size. | Steam 登录必须使用桌面壳。<br>Required for Steam login. |

## 环境要求 / Requirements

- Windows 10/11；桌面版需要 Microsoft Edge WebView2 Runtime。<br>Windows 10/11; desktop use requires Microsoft Edge WebView2 Runtime.
- Python 3.13
- Node.js 24
- npm 11

## 安装 / Install

克隆仓库后，安装 Python 开发依赖和 Web 工作区依赖：

After cloning the repository, install the Python development dependencies and Web workspace dependencies:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
npm ci
```

需要 Steam 登录或桌面壳时，安装可选桌面依赖：

Install the optional desktop dependency when you need Steam login or the desktop shell:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[desktop]"
```

## 浏览器开发模式 / Run In Browser Development Mode

在仓库根目录打开两个 PowerShell 窗口。

Use two PowerShell windows from the repository root.

启动 API / Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn skinflow_api.main:app --app-dir apps/api --host 127.0.0.1 --port 58150
```

启动 Web 客户端 / Start the Web client:

```powershell
npm run dev:web
```

打开 npm 输出的 Vite 地址，通常为 `http://127.0.0.1:5173`。API 健康检查为 `http://127.0.0.1:58150/api/health`，接口文档为 `http://127.0.0.1:58150/api/docs`。

Open the Vite URL printed by npm, normally `http://127.0.0.1:5173`. The API health endpoint is `http://127.0.0.1:58150/api/health`, and the API documentation is `http://127.0.0.1:58150/api/docs`.

浏览器开发模式支持公开行情扫描，但会刻意禁用 Steam 登录。库存同步和挂单操作请使用桌面壳。

Browser development mode supports public market scanning, but deliberately does not open Steam login. Use the desktop shell for Steam inventory and listing operations.

## 桌面版 / Run The Desktop Shell

先构建 Web，再启动桌面入口：

Build the Web application, then start the desktop entry point:

```powershell
npm run build
.\.venv\Scripts\python.exe apps/desktop/launch.py
```

桌面壳会启动仅绑定到本机回环地址的 API，并打开 WebView2 窗口。每次启动都会生成新的本地启动令牌，因此此模式不需要另行运行 Vite 或 Uvicorn。

The desktop shell starts a loopback-only API server and opens a WebView2 window. It uses a fresh local startup token for each launch, so Vite and a separate Uvicorn process are not needed in this mode.

## 典型流程 / Typical Workflow

1. 使用 **扫描 / Scan** 观察公开市场机会。<br>Use **Scan** to inspect public market opportunities.
2. 启动桌面版并通过官方 Steam 登录窗口完成登录。<br>Start the desktop shell and sign in through the official Steam login window.
3. 刷新 **库存 / Inventory**，选择可交易资产。<br>Refresh **Inventory** and select tradable assets.
4. 创建并明确确认挂单预览。<br>Create and explicitly confirm a listing preview.
5. 观察后台提交进度，并自行完成 Steam 手机确认。<br>Watch background submission progress and complete any Steam mobile confirmation yourself.
6. 使用 **挂单 / Listings** 对账真实 Steam 状态、处理待确认项目或取消符合条件的挂单。<br>Use **Listings** to reconcile real Steam states, retry pending work, or cancel eligible listings.
7. 使用 **持仓 / Holdings** 记录买入和真实成交；已提交挂单不等同于已成交。<br>Use **Holdings** to record purchases and actual sales. A submitted listing is not treated as a completed sale.

## 本地数据与隐私 / Local Data And Privacy

- 本地数据库、日志、缓存、构建产物、`.env` 和 `data/` 均被 Git 忽略，禁止提交。<br>Local databases, logs, caches, build output, `.env` files, and `data/` are ignored by Git and must not be committed.
- 正常桌面模式下，Steam 会话会保存到本地 `data/steam_session.bin`，由当前 Windows 用户的 DPAPI 加密以支持重启恢复；清除 Steam 会话会删除该文件。开发测试使用纯内存会话。<br>In normal desktop mode, the Steam session file is stored locally as `data/steam_session.bin`, encrypted with Windows DPAPI for the current Windows user. Clearing the Steam session removes it. Development tests use an in-memory session.
- Steam 凭据不会上传到本仓库。请勿向 issue、release 或聊天中附带本地 `data/`、日志或含账号信息的截图。<br>Steam credentials are never sent to this repository. Do not attach your local `data/` directory, log files, or screenshots containing account data to issues, releases, or chats.
- `SKINFLOW_CSQAQ_API_TOKEN` 可通过用户环境变量或本地 `.env` 提供；两者均不应提交。<br>`SKINFLOW_CSQAQ_API_TOKEN` can be supplied through the user environment or a local `.env`; neither belongs in Git.
- Skinflow 从不自动完成 Steam 手机确认。<br>Steam mobile confirmations are never performed automatically by Skinflow.

## 导入旧账本 / Import A Legacy Ledger

迁移是幂等的，会记录源文件 SHA-256 和迁移版本。使用明确的源库与目标库路径执行一次：

The migration is idempotent and records the source SHA-256 plus migration version. Run it once with explicit source and destination paths:

```powershell
.\.venv\Scripts\python.exe apps/api/scripts/migrate_legacy_ledger.py <legacy-ledger.db> data\skinflow.db
```

## 验证 / Verify

在集成功能模块或创建发布前运行完整检查：

Run the complete local check suite before integrating a module or creating a release:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check apps
npm run test
npm run typecheck
npm run lint
npm run build
```

## 开发边界 / Development Boundaries

Skinflow 按用户能力拆分开发。开始修改前请阅读 [AGENTS.md](AGENTS.md) 和 [模块边界文档 / module boundaries](docs/architecture/module-boundaries.md)。Inventory、Scan、Listings、Ledger、Settings/Auth 应保持隔离；共享 API、路由、配置和组件契约由协调者处理。

Skinflow is developed by capability. Read [AGENTS.md](AGENTS.md) and [module boundaries](docs/architecture/module-boundaries.md) before making changes. Keep Inventory, Scan, Listings, Ledger, and Settings/Auth work isolated; send shared API, routing, configuration, and component contract changes through the coordinator.
