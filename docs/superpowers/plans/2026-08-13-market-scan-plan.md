# Skinflow 行情与扫描模块实施计划

## 目标

实现第一条真实业务链路：通过 csqaq API Token 获取候选，匿名读取 BUFF 首批公开在售和 Steam 公开盘口，计算 1 至 10 件三条价格曲线，并通过 `/api/scans` 与 SSE 提供给前端。

本阶段不实现库存、持仓、挂单、历史和旧账本迁移；不在默认 CI 访问真实平台。

## 固定契约

- 路由固定为 `POST /api/scans`、`GET /api/scans/{job_id}`、`POST /api/scans/{job_id}/cancel`、`GET /api/scans/{job_id}/events`、`GET /api/scans/{job_id}/stream`、`GET /api/scans/{job_id}/results`。
- 每个候选深度上限固定为 10；请求中的 `candidate_limit` 只限制候选数量。
- 请求上限：`candidate_limit <= 200`、`manual_names <= 200`，单个名称长度 <= 200；空字符串/非法名称拒绝，Unicode 规范化后按首次出现顺序去重。
- `NameIdResolver` 属于第一批扫描端口；解析失败写 `candidate.rejected` 和 `STEAM_NAMEID_UNRESOLVED`，不终止任务。
- 首版只支持 `Steam/CS2(appid=730)/CNY(currency=23)`；其他币种返回 `UnsupportedCurrency`。
- `application/scan/service.py` 独占编排；不创建 `application/market/service.py`。
- 每个平台独立 semaphore：csqaq=2、BUFF=2、Steam=4；单请求连接/读取超时 15 秒。
- 429 退避 `min(2^attempt, 60)` 秒并尊重 `Retry-After`；持久化 `upstream.backoff_started/completed`。
- 取消通过共享 cancellation token 终止尚未发出的请求；已返回数据保留并推送，任务终态为 `cancelled`。
- 快照分别保存 csqaq、BUFF、Steam、日成交量的观测时间和 `fee_policy_version`。
- 每个事件 payload 固定带 `schema_version=1`、`job_id`、`sequence`。

## 后端文件

### Domain

- `domain/money/value_objects.py`：CNY 分整数值对象。
- `domain/money/errors.py`：`InvalidMoney`。
- `domain/pricing/fee_policy.py`：按 `(appid, currency)` 选择版本化规则。
- `domain/pricing/fee_calculator.py`：逐件 `max(min_fee, floor(gross * rate))`，拒绝负实收。
- `domain/pricing/errors.py`：`UnsupportedFeePolicy`、`UnreachablePrice`、`BelowMinimumPrice`。
- `domain/pricing/depth.py`：档位差分、展开、逐档累计。
- `domain/pricing/curves.py`：立即求购、推荐挂单、市场在售参考三条曲线。
- `domain/scan/errors.py`：`InvalidStateTransition`。
- `domain/scan/models.py`：任务状态、快照、结果和事件值对象。
- `domain/market/{snapshot.py,tiers.py}`：独立的行情快照和盘口档位模型。

### Application

- `application/scan/models.py`：请求/响应 DTO 与稳定错误码。
- `application/scan/ports.py`：`CandidateSource`、`NameIdResolver`、`MarketDataGateway`、`ScanJobRepository`、`ScanEventRepository`。
- `application/scan/ports.py`：`ScanPersistenceUnitOfWork.persist_result_and_event(...)` 原子提交任务状态、snapshot/result/curve、sequence 和 event。
- `application/scan/service.py`：任务生命周期、候选遍历、并发、取消、退避和结果编排。

### Infrastructure

- `infrastructure/platforms/csqaq/{adapter.py,parser.py}`：Token 认证、候选和缩略图解析。
- `infrastructure/platforms/buff/{adapter.py,parser.py}`：匿名首批在售深度解析，不接受 Cookie。
- `infrastructure/platforms/steam/{adapter.py,parser.py,nameid_resolver.py,nameid_cache.py}`：盘口、日成交量和 nameid 解析。
- `infrastructure/http/{client.py,limiter.py,errors.py}`：超时、semaphore、Retry-After 和结构化上游错误。
- `infrastructure/database/{models.py,session.py,repositories/scan.py,migrations/versions/}`：WAL、外键、事件顺序和快照约束。
- migration 必须创建 `UNIQUE(market_snapshot.id, job_id, market_hash_name)`，并用集成测试验证复合外键。

### Routes/bootstrap

- `routes/scan.py`：只做 DTO 校验和 application service 调用。
- `bootstrap/container.py`：装配具体 adapter、resolver、repository 和 scan service。
- `main.py`：注册扫描路由与 SSE 生命周期。

## 前端文件

```text
features/scan/
  api/{scanApi.ts,scanEvents.ts}
  components/{ScanToolbar,ScanSummary,ScanResultTable,ScanResultRow,ScanResultDetails}
  hooks/{useScanEvents.ts}
  model/{types.ts,formatters.ts}
  pages/{ScanPage.tsx}
  scan.css
  index.ts
```

- `ScanToolbar`：source mode、候选数量、启动/取消。
- `ScanSummary`：任务状态、候选进度、平台观测时间和完整性。
- `ScanResultTable/Row`：流式追加、排序、筛选不重置本地状态。
- `ScanResultDetails`：默认 KPI、1 至 10 曲线和选定数量逐件明细。
- `useScanEvents`：Last-Event-ID 恢复、事件去重和终态处理。
- App router 将扫描页接入真实 `/scan` 路由，其他页面保持当前结构化占位。

推荐价不可用只设置 `recommendation_unavailable` 并将推荐字段置 `NULL`，不丢弃该候选的有效行情结果。

## 测试顺序

1. Domain：金额、手续费、档位展开、三条曲线、推荐挂价和深度不足。
2. Parser fixtures：csqaq、BUFF、Steam 正常/缺字段/限流响应。
3. Application：状态机、NameId 失败隔离、单活跃任务、取消、退避事件、重启恢复。
4. Repository/API：数据库约束、SSE sequence、Last-Event-ID、稳定错误 DTO。
   - 原子 UoW：结果写入成功但 event 写入失败时整体回滚。
   - 并发 sequence 分配不重复，终态事件只能写一次，SSE 只重放已提交事件。
   - 验证 `UNIQUE(id, job_id, market_hash_name)` 和复合外键约束。
5. Frontend：启动/取消、流式行追加、排序筛选稳定、详情展开、深度不足和限流状态。

真实平台 smoke test 单独命令运行，默认 CI 禁止联网。

## 完成标准

- 前端可通过真实 API 启动一次扫描并看到真实平台结果或结构化失败。
- 任何单个候选的 nameid 解析失败不会让整项任务失败。
- 结果可通过 SSE 断线续传恢复，事件顺序和终态可重放。
- 金额和比例可用固定 fixture 逐分复核。
- 所有新增文件低于 400 行，application 不 import infrastructure。
