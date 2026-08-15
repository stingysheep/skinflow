# Skinflow

Skinflow 是一个本机运行的 CS2 半自动交易工作台。当前包含扫描选品、匿名 BUFF/Steam 行情、SSE 事件、旧账本一次性迁移、Steam 单件库存同步、买入/卖出 FIFO 账本、挂单预览与人工确认提交、挂单状态对账和本地启动鉴权。

## 环境

- Python 3.13
- Node.js 24
- npm 11

## 启动开发环境

在项目根目录分别启动 API 和 Web：

```powershell
.\.venv\Scripts\python.exe -m uvicorn skinflow_api.main:app --app-dir apps/api --host 127.0.0.1 --port 58150
npm run dev:web
```

首次迁移旧项目账本（只需执行一次）：

```powershell
\.\.venv\Scripts\python.exe apps/api/scripts/migrate_legacy_ledger.py D:\skinflow\data\ledger.db data\skinflow.db
```

迁移会按源文件 SHA-256 和迁移器版本去重，并保留源库备份与迁移报告。

打开 Vite 输出的本地地址即可。前端 `/api` 请求会代理到 `127.0.0.1:58150`。开发浏览器模式下 Steam 登录按钮会明确提示需要桌面版；行情扫描不需要账号。

桌面外壳需要先安装可选依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[desktop]"
.\.venv\Scripts\python.exe -m skinflow_desktop.launcher
```

生成或更新 Windows 桌面快捷方式（使用新项目图标）：

```powershell
powershell -ExecutionPolicy Bypass -File apps/desktop/tools/create_shortcut.ps1
```

桌面启动器固定绑定回环地址、单进程单 worker，并明确禁用 Uvicorn reload；每次启动会生成新的随机启动令牌，交换为 `HttpOnly; SameSite=Strict` Cookie 后从地址栏移除。桌面模式直接托管 `apps/web/dist`，不需要额外启动 Vite。

Steam 登录只在桌面 WebView2 中打开官方登录页。`steamLoginSecure`、`sessionid` 和 `steamid64` 仅保存在当前进程内存，程序退出即清除；挂单提交不会自动确认 Steam 手机请求，也不会把挂单当成成交。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check apps
npm run test
npm run typecheck
npm run lint
npm run build
```
