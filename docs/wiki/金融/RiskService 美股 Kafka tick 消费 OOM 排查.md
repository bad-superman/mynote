# RiskService 美股 Kafka tick 消费 OOM 排查

## 背景

- **服务:** `risk.risk.service`（RiskService）
- **时间:** 2026-09-14 约 22:52 HKT（美东 10:52，美股常规交易时段）
- **现象:** 进程被 cgroup OOMKill 后反复拉起；贴出来的日志多是启动期 Seata / resolver / gRPC health check，**不是** Go panic 栈。
- **消费:** topic `nasdaq-basic-tick-v2`，group `risk_serice_tick_v1_prod`，**18 分区**，**2 实例**。
- **代码入口:** `internal/consumer/kafka/kafka.go`、`consumer.go`、`handler.go`；价格写入 `internal/data/risk/price_cache.go`。

本文记录排查链路、根因、现网已落地的 Sarama / worker 参数，以及看盘指标。代码以合入 `qa` 的 `7488820` / merge `a7f3a8f` 为准。

## 结论

主因是 **美股全市场 tick 拉取上限过大 + 反压几乎不生效**。积压时仍按单分区最高 50MB 持续 fetch，offset 不前进，进程被灌满后 OOM。

不是主因：末日期权 cron（当时美东窗口外）、gRPC health check unimplemented、Seata TM、Kratos resolver。价格通道 10 万槽位即使打满也只有几十 MB 量级，扛不住这次 RSS。

止血如果 lag 已经上亿：**只缩 fetch 不够**，需要把消费组 reset 到 Latest（或暂停消费）。缩参数只限制「再灌进来的量」。

下面带「推测」的数字（全 topic 约 5 万 QPS）来自 OOM 窗口 lag 增长速度，不是 broker 监控原值。

## 核心步骤

### 1. 先分清「启动日志」和「OOM 现场」

cgroup OOMKill 通常 **没有** Go panic。22:52 附近日志是 Guard 拉起后的：

- Seata `RegisterTMResponse Identified:true`
- resolver `update instances`
- `Subchannel health check is unimplemented`（噪声，不吃内存）

真正有用的是 **重启前后** 的 Kafka / Redis / tick 处理日志，以及 offset / lag。

### 2. 用 lag 判断有没有在消费

OOM 窗口内（Nex / 业务日志，2026-09-14 约 22:32–23:10）：

- `Processing tick`：`messageCount=1`，单分区 lag **约 700 万～1450 万**。每 5 万 offset 才打一次；rebalance 后第一条必打，所以这是 **卡住后的首条**，不是健康追赶。
- 同一 `InitialOffset` 从 22:42 打到 22:59（例如 p0 `175036492`），lag 还在涨（p0 约 1460 万 → 1760 万 / 17 分钟）。
- 重启风暴：实例 A 约 22:52:32、22:57:58；实例 B 约 22:48:22、22:58:55、23:04:05、23:09:24。
- 重启后曾出现 **单实例扛全部 18 分区**；总 lag 量级约 **2e8 条**。
- Kafka：`read tcp …:9092: i/o timeout`，大约每分钟一次，两边实例都有；对应 `Net.ReadTimeout=30s`。
- Redis：`SMEMBERS risk:data:account_ids: i/o timeout`（期权 MM snapshot）。
- 窗口内 **没有** `价格更新通道已满`：堆在通道打满之前就爆了。

**推测（lag 增长反推，不是计量原值）：** 全 topic 约 **3k 条/秒/分区 × 18 ≈ 5 万条/秒**；两实例均分约 2.5 万条/秒/实例。

### 3. 排除其它模块

| 嫌疑 | 结论 |
|------|------|
| 末日期权 | cron 有打点，但 10:52 ET `outside_window` |
| gRPC health check | 只打日志，不占堆 |
| 盘中 EL | 22:47 见 shard `1/1`、0 账户，更像另一实例已死 / Redis 超时 |
| 价格通道 10 万 × 2 套 | 空槽很小；打满也远小于 50MB×分区 fetch |

「2 套」是事实：Wire 港股流一份 `PriceCacheManager`，Kafka `NewDefaultHandler` **再 New 一份**，不是文档里的单例。

### 4. 协议体积：5 万 QPS 不是 50MB/s

`KafkaMsgVoProto` 字段全是 **string**。对典型 AAPL.NB 做 `proto.Marshal`：

| msgType | 典型 payload | 全是 5 万/秒时 |
|---------|--------------|----------------|
| QUOTATION | 68 B | 3.2 MB/s |
| STANDARD | 139 B | 6.6 MB/s |
| REFRESH | 271 B | 12.9 MB/s |
| IRG | 64 B | 3.1 MB/s |
| CHIPPED | 157 B | 7.5 MB/s |

**推测混合** 70% 报价 / 25% 成交 / 5% 快照：均约 **96 B/条**，加 Kafka header+key 约 **115 B** → 5 万 QPS ≈ **5.5 MB/s 全 topic**，约 **0.3 MB/s/分区**。

`Fetch.Max=50MB` 是单分区一次最多灌进客户端的硬顶，不是持续码率。积压时 18 路同时按 Max 灌，进程里可以到几百 MB。

### 5. 改前参数为什么会 OOM

硬编码在 `newSaramaConsumerConfig()` / `tickProcessorWorkerCount`（改前）：

| 参数 | 改前 | 作用 |
|------|------|------|
| Fetch.Min / Default / Max | 1MB / 10MB / **50MB** | 单分区一次最多拉 50MB |
| MaxWaitTime | 100ms | broker 最多等 100ms 就返回 |
| ChannelBufferSize | **1024** | 每分区 Messages 管道深度 |
| MaxProcessingTime | **5min** | 写不满 Messages 时的处理宽限 |
| MaxOpenRequests | **10** | 单连接 in-flight Fetch |
| unmarshal workers | **250** | 异步 unmarshal + HandleTick |
| Heartbeat / Session / Rebalance | 3s / 60s / 90s | 组成员 |
| Offsets.Initial | Newest | 无 committed offset 时从最新开始；**有 committed 则续读** |
| AutoCommit | false | 手动 Mark + 每 500 条或 3s Commit |
| Net.ReadTimeout | 30s | 大 fetch 时容易 i/o timeout |

Sarama 停 fetch 的宽限约为：

```text
MaxProcessingTime × ChannelBufferSize
= 5min × 1024 ≈ 85 小时
```

积压时 ConsumeClaim 在 worker 槽位上堵住，但 85 小时内 **不会停 fetch**，50MB × 多分区 × MaxOpenRequests 继续进进程。

另外：`MarkMessage` 在异步处理 **之前**，处理失败/丢弃也不会挡住 offset 标记（至少一次语义偏弱，OOM 主因仍是 fetch 体积）。

`HandleTick` 对 `updateChan` **非阻塞**（满则丢，打 `价格更新通道已满`）。250 worker 主要是并发 protobuf 对象，不是 Redis IO。Redis 侧仍是 **按 symbol EVAL**，不是 pipeline。

### 6. GOMAXPROCS 与 CPU quota

- OOM 当天 stderr：`Leaving GOMAXPROCS=1: CPU quota undefined`
- 次日可见：`Leaving GOMAXPROCS=8: CPU quota undefined`

`Leaving` = automaxprocs **没有从 cgroup 改 P 数**。`CPU quota undefined` = K8s **没有 `limits.cpu`**（只有 request 也不算 quota）。成功从 quota 设置会打 `Updating GOMAXPROCS=N: determined from CPU quota`。

8 个 P 不能单独清掉上亿 lag；不缩 fetch，追赶时仍可能 OOM。

## Kafka 消费端现网设置（已合 qa）

代码：`internal/consumer/kafka/kafka.go` `newSaramaConsumerConfig()`，worker：`tickProcessorWorkerCount = 64`。启动日志：`Kafka consumer sarama config: ...`。

| 参数 | 改前 | 现网 | 设计意图 |
|------|------|------|----------|
| Fetch.Min | 1MB | **16KB** | 小批次即可返回 |
| Fetch.Default | 10MB | **256KB** | 约 2k 条/次（按 ~115 B/条） |
| Fetch.Max | 50MB | **1MB** | 单分区硬顶；9 分区满载约 9MB，不是 450MB |
| ChannelBufferSize | 1024 | **256** | 降低管道深度 |
| MaxProcessingTime | 5min | **100ms** | 反压窗口约 **25.6s** |
| MaxOpenRequests | 10 | **2** | 限制 in-flight Fetch |
| workers | 250 | **64** | 非阻塞 HandleTick，够约 25k msg/s/实例 |
| MaxWaitTime | 100ms | 不变 | |
| Heartbeat / Session / Rebalance | 3s / 60s / 90s | 不变 | |
| Offset / AutoCommit / ReadTimeout | Newest / 手动 / 30s | 不变 | |

价格通道本身未改：`updateChan=100000`，flush 100ms / 5000 symbol，50 个 Redis worker。Kafka handler 使用 `NewUSKafkaPriceCacheManager`（指标 `source=us_kafka`），港股仍是 Wire `source=hk`。

## 常见坑

1. **Sticky rebalance 会把卡住的 offset 粘回去。** 重启若不 reset group，还是从旧 committed offset 追。
2. **`OffsetNewest` 只对没有 committed offset 生效。** 生产组已有位点，会续读积压。
3. **日志 `lag` 每 5 万 offset 才打。** rebalance 后第一条必打，容易误判成「正在追」；要以 **offset 是否随时间前进** 为准。
4. **`skipped` 不是消费失败。** protobuf 解开了，但 `extractTick` 返回 nil：CHIPPED / OFFCLOSE、空成交价/空买卖价等。有一定比例是预期。`empty` = Value nil；`unmarshal_error` = 解不开。
5. **两套 PriceCacheManager。** 指标必须带 `source`，不要当成一个通道。
6. **夜莺 `nex monitor map` 可能是空的。** 这次主要靠日志 + lag，没有可靠 RSS 曲线。

## 验证

部署后看启动日志里的 fetch/worker 是否已是上表。

Prometheus（`:9999/metrics`）：

```promql
# 分区消费速度
sum by (partition) (rate(risk_kafka_tick_consumed_total[1m]))

# 堆积；应下降或维持很低，不应百万级横着
risk_kafka_tick_lag

# 处理结果；ok 应占多数，skipped 可有稳定比例
sum by (result) (rate(risk_kafka_tick_process_total[5m]))

# 价格通道打满丢弃（OOM 窗口里这条原先打不出来）
rate(risk_price_update_dropped_total[1m])

# Redis 写入 P99
histogram_quantile(0.99, rate(risk_price_update_write_duration_seconds_bucket[5m]))
```

日志侧：offset 前进；不再每分钟 `read tcp …:9092: i/o timeout`；不再 5 分钟一轮 Guard 重启。

## 回退

参数全在 `newSaramaConsumerConfig()` 和 `tickProcessorWorkerCount`。回退即恢复：

- Fetch 1MB / 10MB / 50MB
- ChannelBufferSize 1024
- MaxProcessingTime 5m
- MaxOpenRequests 10
- workers 250

**不要**在未清 lag 的情况下回退，容易再次 OOM。

若必须清积压（需运维明确操作）：

- 暂停消费，或把 group `risk_serice_tick_v1_prod` **reset 到 Latest**
- 接受 reset 之后到当前之间的 tick 不会回放

平台侧建议（代码未改部署）：`limits.cpu` + `limits.memory` 一起设，让 automaxprocs 打出 `Updating GOMAXPROCS=N`；例如 CPU request 4 / limit 8，内存需按缩 fetch 后的 RSS 再定。
