# Skinflow 阶段 3：基础骨架与最小闭环实施计划

## 目标

建立可持续扩展的新工程骨架，并验证一个最小端到端闭环：FastAPI 提供健康状态，React 通过统一 API client 获取并显示状态。此阶段不实现扫描、账本、库存或挂单业务。

## 文件与模块

### 根目录

- `package.json`：统一前端开发、测试、类型检查和构建命令。
- `pyproject.toml`：Python 版本、生产/开发依赖、pytest 与静态检查配置。
- `.editorconfig`：编码和换行规范。
- `.gitignore`：构建产物、虚拟环境、缓存和本地数据。
- `README.md`：开发启动与验证命令。

### 后端 `apps/api/skinflow_api`

- `main.py`：FastAPI app factory，仅注册中间件、路由和生命周期。
- `bootstrap/container.py`：composition root，首版装配 health service。
- `application/health/service.py`：健康查询用例。
- `application/health/models.py`：application 输出模型。
- `routes/health.py`：`GET /api/health` DTO 与 HTTP 映射。
- `settings.py`：非敏感运行配置。
- `tests/test_health_api.py`：最小 API 契约测试。

依赖方向：`routes -> application`；`bootstrap` 装配 service；application 不引用 FastAPI 或 infrastructure。

### 前端 `apps/web`

- `src/app/router.tsx`：TanStack Router 根路由。
- `src/app/providers.tsx`：QueryClient 与 Router provider。
- `src/app/AppShell.tsx`：桌面工作台壳。
- `src/features/system-status/api.ts`：健康接口请求。
- `src/features/system-status/SystemStatus.tsx`：最小状态组件。
- `src/shared/api/client.ts`：唯一 fetch 边界与结构化错误。
- `src/shared/components/*`：仅实现当前实际使用的 Button/StatusBadge 等基础组件。
- `src/styles/tokens.css`：已批准的颜色、字体、间距、圆角、边框和动效 Token。
- `src/styles/globals.css`：reset 与全局排版。
- `src/test/*`：Vitest setup。
- `src/features/system-status/SystemStatus.test.tsx`：健康状态加载/成功/错误测试。

依赖方向：`app -> features -> shared`。Shared 不引用 feature。

### 桌面 `apps/desktop/skinflow_desktop`

- `launcher.py`：单实例、端口选择、随机启动令牌、FastAPI server 生命周期和 pywebview 入口。
- `tests/test_launcher.py`：端口探测与令牌生成的纯逻辑测试。

桌面层只启动和承载应用，不包含业务规则。

## 最小闭环

1. FastAPI `GET /api/health` 返回固定 schema：服务状态、API 版本、运行模式。
2. Vite 开发代理将 `/api` 转发给 FastAPI。
3. TanStack Query 请求健康接口。
4. AppShell 显示导航骨架、当前阶段和后端连接状态。
5. API 停止时显示结构化错误状态，不抛出未处理异常。

## 非目标

- 不创建扫描表和 SSE。
- 不创建业务数据库表。
- 不连接 csqaq、BUFF 或 Steam。
- 不迁移旧账本。
- 不实现完整 shadcn 组件库，只添加当前骨架使用的最小组件。
- 不打包安装程序。

## 验证

- Python：`pytest`、Ruff。
- 前端：Vitest、TypeScript、ESLint、Vite production build。
- 结构：单文件行数检查、前端 feature 边界检查。
- 端到端：同时启动 API 与 Vite，浏览器验证 1440x900 和 1280x800。
- 视觉：截图检查无重叠、无页面级横向滚动、字体和语义色来自 Token。
- 停服验证：后端停止后，前端显示明确离线状态。

## 完成标准

- 新开发者按 README 可启动前后端。
- 所有自动化检查通过。
- 浏览器可以看到工作台骨架和真实后端健康状态。
- API 不可用时 UI 有清晰降级。
- 无文件超过 400 行，无跨层违规引用，无临时代码残留。
