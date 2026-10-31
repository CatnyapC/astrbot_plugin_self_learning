# Module 08 - Data Access Strategy

## 目标
为 `Humee Backend` 明确独立后的数据接入主方案，并给出可执行的最小实现路径。

## 结论（采用）
- 主方案：**结构化读库 + Outbox 事件表增量消费**
- 日志：仅用于排障，不作为主数据源

## 方案对比（简版）
- 读日志：
  - 优点：无需改表
  - 缺点：格式脆弱、解析成本高、难做稳定回放
- 直读业务表（无 Outbox）：
  - 优点：实现简单
  - 缺点：实时增量定位困难，易漏/重处理
- 读库 + Outbox（推荐）：
  - 优点：稳定、可追溯、低复杂度实现实时增量
  - 缺点：需要增加事件写入与消费位点管理

## 最小接入流程
1. 三插件（thread writer / thread router / auto impression card）在关键动作后写入 `ops_event_outbox`
2. `Humee Backend` 后台 worker 按 `id` 增量拉取事件
3. 事件标准化后写入查询表（token/cursor/decision/prompt_trace）
4. 更新 `ops_consumer_cursor.last_event_id`
5. API 提供 `/api/ops/sync_status` 暴露 lag

## 最小字段规范

### OutboxEvent
- `id` (number, required)
- `event_type` (string, required)
- `group_id` (string, optional)
- `trace_id` (string, optional)
- `source` (string, required)
- `payload_json` (string, required)
- `created_at` (number, required)

### ConsumerCursor
- `consumer_name` (string, required)
- `last_event_id` (number, required)
- `updated_at` (number, required)

## 运维指标建议
- `outbox_lag_events`
- `outbox_consume_qps`
- `outbox_consume_error_total`
- `outbox_last_sync_ts`

## 自学习插件参考文件（绝对路径）
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/services/database/sqlalchemy_database_manager.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/repositories/base_repository.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/services/monitoring/collector.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/services/monitoring/metrics.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/services/hooks/perf_tracker.py`
