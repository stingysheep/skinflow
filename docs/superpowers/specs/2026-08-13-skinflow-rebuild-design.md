# Skinflow CS2 半自动交易工作台重建设计

## 1. 文档状态

- 日期：2026-08-13
- 状态：阶段 1（需求与视觉基线）和阶段 2（技术栈与架构）已确认
- 旧项目：`D:\skinflow`，只作为领域规则、迁移数据和回归测试参考
- 新项目：当前仓库，从空白工程开始建设

本设计是后续实施计划的唯一需求与架构基线。任何改变业务口径、跨层依赖、数据库约束或写操作安全边界的实现，都必须先更新本设计或新增 ADR。

## 2. 产品定位与范围

Skinflow 是单用户、本地运行的 CS2 半自动交易工作台。完整工作流为：

1. 扫描选品
2. 线下买入并记账
3. Steam 到货识别
4. 持仓与价格监控
5. 选择库存资产并预览挂单
6. 人工确认后提交 Steam 挂单
7. 成交记录与历史复盘

扫描选品是最高频场景。首版只支持 CS2（Steam appid 730），不为 Dota 2 或 TF2 提前增加页面和兼容逻辑。

保留旧项目的以下能力：

- 访问 csqaq 获取候选、名称、图片与聚合行情
- 匿名访问网易 BUFF 的当前卖单与最多 10 件可见深度
- 匿名访问 Steam 市场的求购、在售、盘口深度和日成交量
- Steam 手续费、逐件价格、累计成本、累计实收和比例计算
- 买入批次、成交回报、持仓、库存和挂单记录

不在扫描阶段使用网易 BUFF 或 Steam 账号凭据。Steam 会话只用于必要的库存读取和人工确认挂单。

## 3. 协作与工程规则

- 严格按阶段推进，一个阶段经用户批准后才能进入下一阶段。
- 写代码前必须先说明新增或修改文件、模块依赖、复用点和测试方案。
- 单文件 350 行预警，400 行禁止合入。
- 相同 UI 或业务逻辑出现第二处时提取公共能力。
- 禁止跨 feature 无序引用；公共模块不得反向引用业务 feature。
- 所有视觉参数由 Design Token 提供，组件内禁止硬编码色值和尺寸魔法数。
- 优先使用既定组件库的原生能力，不重复制造基础控件。
- 每完成 2 至 3 个业务功能，执行依赖、重复代码、未使用代码和文件行数巡检。
- Figma 可用时，以批准的 Figma Variables 和组件参数为准。
- `ui-ux-pro-max` 只作为设计研究和审查输入，不覆盖业务需求、Figma 或项目 Token。

## 4. 视觉与交互基线

### 4.1 视觉方向

- 默认且仅提供浅色主题。
- 气质为克制、专业的数据工具，不使用游戏化装饰、渐变或营销页面构图。
- 中性浅灰作为页面背景，白色作为主要内容面。
- 蓝色表示交互、链接和当前选中。
- 绿色表示比例达标或操作可执行。
- 橙色表示深度不足、数据待确认、限流或排队风险。
- 红色表示错误、超限或不可执行。
- 饰品缩略图承担 CS2 识别感，稀有度颜色不承担业务状态语义。

### 4.2 字体与数字

- 正文、标题、饰品名称：IBM Plex Sans。
- 价格、数量、比例、时间：IBM Plex Mono。
- 数字使用 tabular/等宽字形，保证表格纵向对齐。

### 4.3 布局

- 1440px 为完整桌面工作区基线。
- 1280px 为主要笔记本可用下限。
- 扫描结果采用高密度数据表，详情在行内展开。
- 1280px 下保留全部字段，表格容器独立横向滚动；页面本身不得被撑宽。
- 扫描结果流式追加时，不能打断用户正在进行的排序、筛选或详情查看。

## 5. 扫描产品行为

### 5.1 候选与运行方式

- 默认由 csqaq 提供候选和初始排序。
- 支持导入手动饰品名称清单。
- `hybrid` 模式合并两类来源，并按 `market_hash_name` 去重。
- 每个扫描候选固定分析最多 10 件。
- 发现一个有效结果就立即持久化并推送到主表。
- Steam、BUFF、csqaq 分别管理缓存、并发预算和退避。
- 不采用每件固定睡眠数秒的串行模式；采用有限并发，并在 `429` 时自适应退避。
- Steam 日成交量遇到限流时，不阻塞价格结果，后续以事件补充。

### 5.2 主表字段

- 物品名称与缩略图
- BUFF 最低在售价
- Steam 最高求购价
- Steam 最低在售价
- 最低价口径的立即求购比例
- 最低价口径的推荐挂单预估比例
- Steam 日成交量
- 数据完整性与上游状态

主表只使用第 1 件的 BUFF 最低价做快速筛选，不把最低价命名为 10 件真实均价。

### 5.3 详情 KPI 与渐进披露

详情顶部默认显示：

1. BUFF 最低价
2. Steam 最高求购价
3. Steam 最低在售价
4. 10 件最佳累计比例

其下展示立即求购与推荐挂单两种完整累计结论，以及 1 至 10 件累计曲线。用户选择某个数量后，才展开对应的 BUFF、Steam、手续费和累计金额明细，不默认平铺所有档位。

## 6. 金额、价格与精确计算

### 6.1 Money 模型

```text
Money(amount_minor: int, currency: CNY)
```

- 最小单位为人民币分。
- Domain 和数据库禁止使用浮点金额。
- BUFF 十进制字符串通过 `Decimal` 按明确规则转换为分。
- Steam 价格按接口单位归一化为分。
- 平台适配器负责解析和单位归一化。
- Domain 负责手续费、逐件配对和累计计算。
- Steam 手续费逐件计算并按平台规则取整，禁止先汇总再乘费率。

价格语义必须区分：

- `listing_price`：买家看到或支付的标价
- `trade_price`：实际成交金额
- `seller_proceeds`：扣除平台手续费后的卖家实收
- `buff_ask_price`：BUFF 当前卖单价
- `steam_bid_price`：Steam 求购价
- `steam_ask_price`：Steam 在售价

### 6.2 档位展开

平台档位先展开为逐件价格序列。例如：

```text
BUFF: 1.12 x 3, 1.13 x 5, 1.16 x 2
展开: [1.12, 1.12, 1.12, 1.13, 1.13, 1.13, 1.13, 1.13, 1.16, 1.16]
```

Steam 求购按价格从高到低展开；Steam 在售按价格从低到高展开。

### 6.3 三条曲线

```text
立即求购比例(n)
= BUFF 前 n 件累计成本
  / Steam 前 n 高求购逐件扣费后的累计实收
```

该路径可立即执行，但受 Steam 求购深度限制。

```text
推荐挂单预估比例(n)
= BUFF 前 n 件累计成本
  / 推荐挂价逐件扣费后的预计累计实收
```

该路径具有操作意义，但成交和 ETA 都属于预估。

```text
市场在售参考比例(n)
= BUFF 前 n 件累计成本
  / Steam 前 n 低在售价逐件扣费后的参考累计实收
```

Steam 在售档位是竞争挂单，不是保证收入。该曲线只在详情作为市场空间对照，不进入主表 KPI。

深度不足时只计算实际可见数量。后续点位为 `NULL`，不得外推、填零或使用旧快照冒充实时数据。

## 7. 技术栈

### 7.1 前端

- React + TypeScript + Vite
- TanStack Router
- TanStack Query
- TanStack Table
- Zustand，仅用于少量本地 UI 状态
- shadcn/ui + Radix
- ECharts
- Vitest + Testing Library
- Playwright

### 7.2 后端与桌面

- Python 3.13+
- FastAPI
- Pydantic
- SQLAlchemy 2.x，使用显式 repository，不允许 route 或 application 直接持有 ORM session
- Alembic，负责所有版本化 schema migration
- SQLite
- SSE
- pywebview + WebView2
- Windows Credential Manager，通过 `CredentialStore` port 隔离

生产启动后直接打开桌面窗口。开发时 Vite 和 FastAPI 可独立运行，但桌面与浏览器调试共享同一套前端和 API。

## 8. 架构与依赖方向

```text
routes -> application -> domain
             |
             v
      application ports
             ^
             |
 infrastructure adapters

app startup -> bootstrap/composition root -> concrete implementations
```

- `application` 定义 `MarketGateway`、`InventoryGateway`、`ListingGateway`、`ScanJobRepository`、`CredentialStore` 等端口。
- `infrastructure` 实现端口，可依赖 domain 值对象和 application 契约。
- `application` 禁止 import `infrastructure`。
- `bootstrap/container.py` 是唯一 composition root。
- routes 只接收已装配的 application service，不看见具体 SQLite 或平台 adapter。
- domain 不依赖 FastAPI、SQLite、HTTP 或平台响应结构。

`capabilities()` 只返回静态能力，例如 `PUBLIC_ASKS`、`PUBLIC_BIDS`、`DAILY_VOLUME`、`INVENTORY`、`SUBMIT_LISTING`。登录失效、限流和维护属于运行时状态，通过结构化错误或健康状态表达。

## 9. 目录结构与模块治理

```text
apps/web/src/
  app/{router,providers,shell}
  features/{scan,inventory,holdings,listings,history,settings}
  shared/{api,components,formatting,hooks,types}
  styles/{tokens.css,globals.css,themes.css}

apps/api/skinflow_api/
  routes/
  application/{scan,inventory,holdings,listings,migration}
  domain/{money,pricing,scan,portfolio,listing}
  infrastructure/{database,credentials,http,platforms}
  bootstrap/container.py
```

前端依赖方向为 `app -> features -> shared`。Feature 只能通过公共入口协作，`shared` 禁止引用 feature。后端 route 不写 SQL，repository 不计算比例，platform parser 与 transport 分文件，DTO 与 domain model 分离。

## 10. 扫描状态机与运行约束

```text
queued -> running -> succeeded
                  -> failed
                  -> cancelling -> cancelled
queued -> cancelled
```

- `cancelled`、`succeeded`、`failed` 为终态，不允许再次转换。
- 同时只允许一个 `queued/running/cancelling` 任务。
- 生产强制单进程、单 worker、单实例锁。
- 禁用 Uvicorn 多 worker 和后端开发重载，避免任务重复执行；Vite HMR 不受影响。
- 应用重启后，`queued/running` 标记为 `failed(APP_RESTARTED)`，`cancelling` 标记为 `cancelled`。
- 已产生的结果和事件全部保留。
- “继续扫描”创建关联的新任务，不复活旧任务。

## 11. SSE 与持久化事件

事件包括：

```text
job.created
job.started
candidate.accepted
candidate.rejected
result.created
volume.pending
volume.updated
upstream.rate_limited
job.cancelling
job.cancelled
job.succeeded
job.failed
```

- 每个任务的 `sequence` 严格单调递增。
- `UNIQUE(job_id, sequence)` 由数据库保证。
- SSE `id` 等于 sequence。
- 前端优先使用 `Last-Event-ID`，补偿接口支持 `?after=`。
- 结果、任务状态与对应事件必须在同一事务提交。
- 完成、失败、取消、限流、退避和阶段切换事件都持久化。
- 终态事件只能写一次；任务结束后仍可重放全部历史事件。

## 12. 平台适配器与统一错误

业务层不得解析平台响应文本。Adapter 将底层异常转换为稳定的结构化错误。

- Domain：`InvalidMoney`、`InvalidListing`、`InvalidStateTransition`
- Application：`RateLimited`、`SessionExpired`、`AuthenticationRequired`、`UpstreamUnavailable`、`MalformedUpstreamResponse`、`Conflict`、`UnsupportedCapability`
- Infrastructure：HTTP、解析、SQLite、密钥环原始错误，仅在 adapter 内部存在

原始平台响应只能进入脱敏、短期诊断日志，不进入业务表或前端状态。

## 13. 本地鉴权与凭据

- 服务只绑定 `127.0.0.1`，不开放局域网。
- 每次桌面启动生成新的随机令牌。
- 首次访问用令牌换取 `HttpOnly; SameSite=Strict` Cookie。
- 精确校验当前回环地址、动态端口的 `Origin` 和 `Host`。
- 浏览器写接口只接受 `application/json`，缺失或错误 Origin 时拒绝。
- 本地 HTTP 不虚假设置不可用的 `Secure` Cookie；安全边界依赖回环绑定、随机令牌和 Origin 校验。
- 敏感凭据存 Windows Credential Manager，配置文件只保存非敏感配置。
- Steam 密码不经过应用；通过独立应用内窗口打开 Steam 官方登录页，支持 Steam Guard 和二维码。
- 手机确认继续由 Steam App 完成。

## 14. 数据库约定

SQLite 启用：

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
```

- 时间统一存 UTC Unix 毫秒整数。
- 金额统一存 CNY 分整数。
- 比例统一存 ppm 整数，`1.0 = 1,000,000`。
- ID 使用 UUID 字符串。
- 使用版本化 migration，禁止启动时临时 ALTER。

### 14.1 扫描核心约束

- `scan_job` 包含状态、来源、固定目标数量 10、结果数量、过滤条件、事件序号、失败安全信息和乐观锁版本。
- 部分唯一索引保证只有一个活跃扫描任务。
- `scan_event(job_id, sequence)` 唯一。
- `market_snapshot` 保存归一化的 BUFF ask、Steam bid、Steam ask 档位和各自抓取时间。
- `market_tier(snapshot_id, side, position)` 为主键。
- `scan_result.snapshot_id` 非空。
- 复合外键 `(snapshot_id, job_id, market_hash_name)` 保证结果只能引用同任务、同饰品快照。
- `price_curve_point(snapshot_id, quantity)` 保存 1 至 10 件三条曲线，深度不足字段为 NULL。

### 14.2 账本

- `purchase_lot` 保存买入批次、数量、单位成本、时间和平台。
- `sale_fill` 追加保存每次成交的批次、数量、实际实收和可选成交总额。
- 剩余数量由 lot 数量减 fill 数量实时推导，不冗余存储。
- 事务内验证累计售出数量不能超过买入数量。

### 14.3 库存身份

Steam 资产使用复合身份：

```text
(platform, appid, contextid, assetid)
```

`inventory_asset` 以此为主键。库存刷新不删除消失资产，而是标记 `missing/listed/sold`，保留历史引用。

### 14.4 挂单幂等与唯一性

- `listing_preview` 只保存预览生命周期，不在预览头部绑定单个行情快照。
- 每个 `listing_preview_item` 必须通过非空 `market_snapshot_id` 引用该饰品自己的定价输入；一个批量预览可以包含多个不同快照。
- `listing_preview_item` 的 `market_hash_name` 必须与所引用快照一致，由复合外键保证。
- `listing_request.idempotency_key` 全局唯一。
- `listing_item` 使用 `UNIQUE(request_id, platform, appid, contextid, assetid)`。
- 部分唯一索引保证同一复合资产在 `submitting/submitted/pending_confirmation/active` 状态下只有一条活跃挂单。
- Steam 挂单提交不自动重试。网络结果不确定时进入待对账错误，不直接再次提交。

## 15. 挂单工作流

库存按单件复合资产身份勾选，可选择 1 件或多件。统一流程为：

1. 选择资产
2. 创建持久化预览
3. 默认填入推荐挂价
4. 可批量统一调整
5. 可逐件覆盖价格
6. 即时重算手续费、预计实收、成本比例和风险
7. 提交前重新校验 Steam 盘口、预览有效期和会话
8. 用户明确确认
9. 逐件提交并逐件返回结果

同一批次部分成功时状态为 `partially_submitted`，不能用单个布尔值掩盖单件失败。

Steam 售出后，按 FIFO 将资产归属到未售 purchase lot，创建一个或多个 sale fill，并在同一事务更新库存和挂单状态。FIFO 是明确业务规则，不宣称能还原旧 BUFF 订单与 Steam assetid 的精确对应。

## 16. 一次性旧账本迁移

迁移不进入日常启动路径，由实施阶段执行一次：

1. 对旧 `ledger.db` 做只读备份。
2. 计算源文件 SHA-256 和 schema 指纹。
3. 使用 staging 或单事务导入新 schema。
4. 保留 lot/fill 关系、成本、平台、时间、成交和剩余持仓。
5. 核对 lot 数、fill 数、买入件数、买入成本、售出件数、实收金额和逐 lot 剩余数量。
6. 全部一致后写入 completed 状态。

`migration_run` 使用 `(source_sha256, migrator_version)` 唯一。迁移控制记录与业务导入使用分离事务：先提交 `running` 记录，再在独立事务或 staging 表中导入业务数据。校验失败时回滚目标业务数据，随后单独提交 `failed` 状态并保留备份和报告；不得写 `completed_at`。修复后的新迁移器版本允许重新运行，但不能重复导入相同版本。

行情缓存不迁移，按新 schema 重建。

## 17. API 契约

核心路由：

```text
POST   /api/scans
GET    /api/scans/{job_id}
POST   /api/scans/{job_id}/cancel
GET    /api/scans/{job_id}/events
GET    /api/scans/{job_id}/stream
GET    /api/scans/{job_id}/results

GET    /api/inventory
POST   /api/inventory/refresh

POST   /api/listing-previews
POST   /api/listing-requests
GET    /api/listing-requests/{id}

GET    /api/holdings
POST   /api/purchases
POST   /api/sales
GET    /api/history

GET    /api/settings
PATCH  /api/settings
GET    /api/platform-health
```

扫描目标数量固定为 10，不允许客户端修改。DTO 使用稳定字段和枚举，不直接暴露数据库 row 或 domain object。

统一错误响应：

```json
{
  "error": {
    "code": "UPSTREAM_RATE_LIMITED",
    "message": "Steam 行情接口正在限流",
    "retryable": true,
    "retry_after_seconds": 18,
    "correlation_id": "..."
  }
}
```

前端只判断稳定的 `code`，不解析中文 message。

## 18. 错误处理

- 上游失败按平台隔离，单个平台失败不导致整次扫描崩溃。
- 扫描结果标记完整、成交量待补、部分缺失或失败。
- `429` 自动退避并显示预计恢复时间。
- 普通只读请求可按策略重试；有副作用的 Steam 挂单默认不重试。
- SSE 断线自动以事件 ID 重连。
- 应用重启将未完成任务明确终止，不隐式重复执行。
- 所有写操作使用数据库事务和幂等键。
- Cookie、Token 和凭据统一脱敏。

## 19. 测试与持续巡检

- Domain：纯单元测试，覆盖金额、手续费、档位展开、逐件配对、累计比例、状态机、持仓和挂单计划。
- Application：假 gateway 和 repository，覆盖扫描、缓存、事件、取消、迁移、库存和挂单预览。
- Infrastructure：SQLite migration、HTTP parser、限流、密钥环和 adapter 集成测试。
- API：DTO、错误码、Origin 校验、SSE 断线恢复和鉴权测试。
- Frontend：Vitest + Testing Library，覆盖排序、筛选、流式追加、详情展开和挂单预览。
- E2E：Playwright 覆盖扫描、查看详情、库存选择和挂单预览。
- 真实 Steam、BUFF、csqaq 请求只在手动 smoke 测试执行，不进入默认 CI。
- CI 检查单文件行数、循环依赖、非法跨 feature import、重复逻辑和未使用代码。

## 20. 非目标

- 首版不支持 Dota 2、TF2 或多人账户。
- 不开放局域网或公网访问。
- 不自动执行买入。
- 不自动确认 Steam 手机令牌。
- 不在重启后自动续跑扫描任务。
- 不使用 Redis、Celery 或多 worker。
- 不把竞争卖单价格描述为保证成交收入。
- 不迁移旧行情缓存。

## 21. 分阶段实施顺序

1. 工程骨架、依赖规则、Design Token、请求封装和测试基线
2. 公共基础组件和桌面外壳
3. 扫描任务、匿名平台适配器、SSE 和高密度结果表
4. 10 件累计详情与价格曲线
5. 一次性旧账本迁移、持仓和历史
6. Steam 登录、库存同步与复合资产身份
7. 挂单预览、调价、幂等提交和对账
8. 全链路巡检、性能验证和发布打包

每个业务模块完成后单独评审，不并行大规模重构和新增需求。
