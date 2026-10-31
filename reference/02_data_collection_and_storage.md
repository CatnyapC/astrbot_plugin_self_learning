# Module 02 - Data Collection and Storage

## 目标
定义“最小可维护”的观测数据落库模型，保证：
- 能支撑实时大屏与历史回放
- 查询简单（按群、按时间、按 trace）
- 先跑通，再扩展

## 数据来源决策
- 主方案：`Humee Backend` 读取 AstrBot 三插件（thread writer / thread router / auto impression card）数据库中的结构化表 + Outbox 事件表。
- 不采用：以日志解析作为主数据来源。
- 原因：结构稳定、可索引查询、支持增量消费与回放。

## 最小 API（数据采集侧）
1. `record_token_usage(event)`
2. `upsert_cursor_state(state)`
3. `record_router_decision(event)`
4. `record_prompt_trace_step(step)`
5. `append_outbox_event(event)`
6. `consume_outbox(last_event_id, limit)`

说明：以上是服务层最小内部 API（Python 方法），供 thread router / auto impression card 等模块调用。

## 字段定义（建议最小表结构）

### Table: `ops_token_usage`
- `id` (int, PK)
- `trace_id` (string, optional)
- `group_id` (string, required, index)
- `source` (string, required): `thread_router` | `auto_impression_card` | `other`
- `prompt_tokens` (int, required)
- `completion_tokens` (int, required)
- `total_tokens` (int, required)
- `model` (string, optional)
- `created_at` (bigint, required, index)

### Table: `ops_cursor_state`
- `id` (int, PK)
- `group_id` (string, required, index)
- `cursor_type` (string, required, index): `thread_router_catchup` | `auto_impression_cursor`
- `cursor_value` (string, required)
- `lag_count` (int, optional)
- `updated_at` (bigint, required, index)

### Table: `ops_router_decision_event`
- `id` (int, PK)
- `trace_id` (string, required, index)
- `group_id` (string, required, index)
- `thread_id` (string, optional, index)
- `message_id` (string, optional, index)
- `case_name` (string, optional)
- `need_reply` (bool, required, index)
- `reason` (text, optional)
- `confidence` (float, optional)
- `latency_ms` (float, optional)
- `created_at` (bigint, required, index)

### Table: `ops_prompt_trace_step`
- `id` (int, PK)
- `trace_id` (string, required, index)
- `group_id` (string, required, index)
- `step_name` (string, required, index): `auto_memory` | `prefetch` | `assembly` | `final_prompt`
- `step_order` (int, required)
- `input_refs_json` (text, optional)
- `output_preview` (text, optional): 脱敏+截断
- `token_estimate` (int, optional)
- `latency_ms` (float, optional)
- `created_at` (bigint, required, index)

### Table: `ops_event_outbox`
- `id` (bigint, PK, auto increment)
- `event_type` (string, required, index): `token.usage` | `cursor.updated` | `router.decision` | `prompt.trace.step`
- `group_id` (string, optional, index)
- `trace_id` (string, optional, index)
- `source` (string, required): `thread_writer` | `thread_router` | `auto_impression_card`
- `payload_json` (text, required)
- `created_at` (bigint, required, index)

### Table: `ops_consumer_cursor`
- `consumer_name` (string, PK): 例如 `humee_backend_main`
- `last_event_id` (bigint, required)
- `updated_at` (bigint, required)

## 最小索引策略
- `ops_token_usage(group_id, created_at)`
- `ops_cursor_state(group_id, cursor_type)` unique
- `ops_router_decision_event(group_id, created_at)`
- `ops_router_decision_event(trace_id)`
- `ops_prompt_trace_step(trace_id, step_order)`
- `ops_event_outbox(id)` PK
- `ops_event_outbox(created_at)`
- `ops_event_outbox(event_type, id)`
- `ops_consumer_cursor(consumer_name)` PK

## 自学习插件参考文件（绝对路径）
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/models/orm/base.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/models/orm/message.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/repositories/base_repository.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/services/database/sqlalchemy_database_manager.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/services/database/facades/metrics_facade.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/services/hooks/perf_tracker.py`
