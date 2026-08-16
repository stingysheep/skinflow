# 模块边界

本文档是 Skinflow 按功能开发时的边界和集成约定。当前代码已经按这些
目录组织；本阶段只建立所有权和依赖规则，不移动源码、不重构业务逻辑。

## 模块地图

| 模块 | 责任 | 主要路径 | 测试路径 |
| --- | --- | --- | --- |
| Inventory 库存 | Steam 单件库存同步、库存分组、资产选择 | `apps/api/skinflow_api/application/inventory/`, `apps/api/skinflow_api/infrastructure/database/inventory.py`, `apps/api/skinflow_api/infrastructure/platforms/steam/inventory.py`, `apps/web/src/features/inventory/` | `apps/api/tests/test_inventory*.py`, `apps/web/src/features/inventory/**/*.test.*` |
| Scan 扫描选品 | 候选来源、行情快照、筛选、SSE 扫描进度 | `apps/api/skinflow_api/application/scan/`, `apps/api/skinflow_api/infrastructure/platforms/`, `apps/api/skinflow_api/routes/scan.py`, `apps/web/src/features/scan/` | `apps/api/tests/test_scan*.py`, `apps/api/tests/test_platform_parsers.py`, `apps/web/src/features/scan/**/*.test.*` |
| Listings 挂单 | 挂单预览、提交、状态查询、对账 | `apps/api/skinflow_api/application/listing/`, `apps/api/skinflow_api/infrastructure/database/listing.py`, `apps/api/skinflow_api/infrastructure/platforms/steam/listing*.py`, `apps/api/skinflow_api/routes/listing.py`, `apps/web/src/features/listings/` | `apps/api/tests/test_listing*.py`, `apps/api/tests/test_steam_listing_adapter.py` |
| Ledger 持仓账本 | 买入/卖出 FIFO、成交记录、待处理买入 | `apps/api/skinflow_api/application/ledger/`, `apps/api/skinflow_api/infrastructure/database/ledger.py`, `apps/api/skinflow_api/routes/ledger.py`, `apps/web/src/features/holdings/` | `apps/api/tests/test_ledger.py`, `apps/web/src/features/holdings/**/*.test.*` |
| Settings/Auth 设置与认证 | 本地偏好、启动鉴权、Steam 会话生命周期 | `apps/api/skinflow_api/application/preferences/`, `apps/api/skinflow_api/infrastructure/preferences/`, `apps/api/skinflow_api/routes/preferences.py`, `apps/api/skinflow_api/routes/local_auth.py`, `apps/api/skinflow_api/routes/steam_session.py`, `apps/web/src/features/settings/`, `apps/web/src/app/bootstrapAuth.ts` | `apps/api/tests/test_preferences.py`, `apps/api/tests/test_local_auth*.py`, `apps/api/tests/test_steam_login*.py`, `apps/web/src/features/settings/**/*.test.*`, `apps/web/src/app/bootstrapAuth.test.ts` |
| Shared Domain 共享领域 | 金额、费用、价格层级、行情快照、挂单领域对象 | `apps/api/skinflow_api/domain/` | `apps/api/tests/test_pricing_domain.py` |
| Desktop Shell 桌面壳 | 本地启动、WebView、图标和快捷方式 | `apps/desktop/` | `apps/desktop/tests/` |
| Web Shared 前端共享层 | API 客户端、通用组件、样式、路由和状态提供器 | `apps/web/src/shared/`, `apps/web/src/app/`, `apps/web/src/styles/` | 对应 `*.test.*` 文件 |

## 依赖方向

```text
Web feature -> feature API client -> API route -> application use case
                                                        |
                                                        v
                                                     domain
                                                        ^
                                                        |
                                      infrastructure adapters/database
```

- `domain` 不依赖路由、数据库、HTTP 或 Web。
- `application` 依赖 `domain`，通过 ports 描述外部能力。
- `infrastructure` 实现 ports，负责 SQLite、网络平台和 Steam/BUFF/悠悠等适配。
- `routes` 只负责 HTTP/SSE 输入输出和错误映射；用例编排留在 application。
- Web feature 不直接拼接平台请求；所有后端通信通过本 feature 的 API client。
- Desktop 只负责进程和窗口生命周期，不复制 API 或 Web 的业务规则。

## 分支与提交

主线为 `master`，保持可运行。功能分支建议使用：

- `feature/inventory`
- `feature/scan`
- `feature/listings`
- `feature/ledger`
- `feature/settings-auth`
- `chore/module-boundaries`、`chore/ruff-format-cleanup` 等维护分支

共享文件由协调分支维护：`pyproject.toml`、根 `package.json`、
`package-lock.json`、API 路由注册、Web router、共享组件/样式、本文档和
`AGENTS.md`。功能分支若需要改变共享契约，应先在提交说明和模块文档中
写清输入、输出、错误形状和兼容策略。

推荐提交类型：`feat(inventory): ...`、`fix(scan): ...`、
`test(listings): ...`、`docs(architecture): ...`、`chore(repo): ...`。

## 集成检查点

每个功能分支至少完成该模块测试；合并前运行：

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check apps
npm run test
npm run typecheck
npm run lint
npm run build
```

远程仓库配置、默认分支保护和 PR 流程在确认目标 `OWNER/REPO` 后执行。
