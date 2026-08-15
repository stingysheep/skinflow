# 扫描筛选与悠悠公开深度实施基线

## 范围

- 扫描操作统一使用“挂底价”和“丢求购”。
- 进货平台允许单选或同时选择网易 BUFF、悠悠有品。
- 支持进货价格区间、最低 Steam 日成交量和候选数量。
- 挂底价只展示挂底价价格与比例；丢求购只展示最高求购价与比例。
- 比例按小数展示，数值越低越优，默认升序。
- 每个结果提供 BUFF、悠悠和 Steam 市场入口。

## 依赖方向

```text
routes -> application/scan -> domain/market + domain/pricing
                            -> application ports
composition root -> infrastructure csqaq/buff/youpin/steam/sqlite
```

悠悠的 Edge/CDP 细节仅存在于 `infrastructure/platforms/youpin`。应用层只接收归一化
`MarketSnapshot`，不解析平台文本，也不依赖桌面壳或具体浏览器实现。

## 上游策略

| 平台 | 并发 | 最小启动间隔 | 依据 |
|---|---:|---:|---|
| csqaq | 1 | 1.25 秒 | 按实测 429 行为保守留出间隔；仍尊重 Retry-After |
| Steam | 4 | 0 | 2026-08-14 匿名盘口实测稳定起点 |
| BUFF | 2 | 0.5 秒 | 并发 3 起出现明显 429 |
| 悠悠 | 2 | 0 | 轻量模式，复用单个 Edge 进程 |

除 csqaq 外，没有把实测值声明为官方配额。每个平台独立限制并发；429 使用
`Retry-After` 或指数退避，并持久化开始/结束事件，一个平台退避不暂停其他平台。

## 悠悠采集边界

1. csqaq 使用 `BUFF-YYYP` 一次请求完成候选初筛并取得 `yyyp_id`。
2. 只有用户勾选悠悠且候选通过初筛时，才按需启动本机 Edge。
3. Edge 正常打开公开商品页，CDP 仅读取页面自己发出的
   `queryOnSaleCommodityList` 成功响应。
4. 阻止图片、字体、视频和统计资源；每个候选最多保留前十件。
5. 页面完成立即关闭，全部请求空闲 60 秒后退出 Edge。
6. 不伪造签名、不逆向 WAF；页面失败只影响对应来源或候选。

## 数据与显示

- 金额继续使用 CNY 分整数。
- `MarketSide.YOUPIN_ASK` 与 `youpin_observed_at` 进入不可变快照。
- 同时选择两个进货平台时，分别抓取后以真实第一档最低价格作为该结果的成本来源。
- 累计曲线严格使用同一进货来源的前十件，不跨平台混单，不补零、不外推。
- `scan_job` 持久化操作模式、平台、价格区间和最低成交量。
- snapshot/result/curve/event 仍由原有 Unit of Work 在同一事务提交。

## 资源控制

- 未选择悠悠时不创建浏览器线程或 Edge 进程。
- 默认最多两个悠悠页面并发，目标额外内存约 180–350 MB。
- 应用退出时 composition root 显式关闭悠悠浏览器资源。
