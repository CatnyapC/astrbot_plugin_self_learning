# Module 09 - Current AstrBot Runtime (Thread Writer + Thread Router + AIC)

## 目标
面向交付团队，清楚说明当前 AstrBot 运行时里：
- Thread Writer 在做什么
- Thread Router 在做什么
- Auto Impression Card (AIC) 在做什么
- Humee Backend 如何在不干预主线的前提下抓取数据

## 对接边界声明
- Humee Backend 运行时只对接三插件：
  - `thread writer`（当前仓库目录名：`astrbot_plugin_thread_archive`）
  - `thread router`
  - `auto impression card`
- `self_learning` 仅参考，不参与运行时对接。

## 零、Thread Writer 当前职责（消息归档底座）
1. 持续写入消息归档库，作为后续关系路由与记忆提取的基础数据源。
2. 维护消息主表与归档表，供上游增量读取。

### 关键运行数据库（只读）
- `/Users/lincoln/Git/AstrBot/data/plugin_data/astrbot_plugin_thread_archive/thread_archive.db`
- `/Users/lincoln/Git/AstrBot/data/plugin_data/astrbot_plugin_thread_archive/llm_trace.db`

### 推荐读取表（只读）
- `messages`
- `messages_archive`
- `image_caption_cache`（若需媒体摘要上下文）
- `llm_trace`（在 `llm_trace.db` 中，补充最终回复与 prompt/usage 观测）

## 一、Thread Router 当前职责（主线快流）
1. 按群消息做关系优先路由，输出 `need_reply` 决策与原因。
2. 维护 catchup 增量追游标（`cursor_ts/cursor_table/cursor_row_id`）。
3. 在 prompt 构建中注入 relation / timeline / auto memory / prefetch 等上下文。
4. 将调试与回放信息写入 trace 库。

### 关键运行数据库（只读）
- `/Users/lincoln/Git/AstrBot/data/plugin_data/astrbot_plugin_thread_router/thread_router.db`
- `/Users/lincoln/Git/AstrBot/data/plugin_data/astrbot_plugin_thread_router/thread_router_trace.db`

### 推荐读取表（只读）
- `message_decisions`
  - 核心字段：`group_id/sender_id/message_id/decision/reason_code/detail_json/model_ver/created_at`
- `online_catchup_state`
  - 核心字段：`group_id/cursor_ts/cursor_table/cursor_row_id/new_count/uncertain_count/updated_at`
- `reply_dispatch_messages`
  - 核心字段：`group_id/sender_id/message_id/case_result/need_reply/has_replied/decision/reason_code/detail_json/updated_at`
- `reply_dispatch_group_cursor`
  - 核心字段：`group_id/cursor_ts/cursor_table/cursor_row_id/updated_at`
- `tool_result_cache`
  - 核心字段：`group_id/sender_id/tool_name/args_json/result_json/created_at`
- `relation_timeline_summary`
  - 核心字段：`group_id/model_ver/summary/topic_tags_json/updated_at`
- `routing_traces`（trace DB）
  - 核心字段：`ts/session_id/group_id/sender_id/prompt/selected_thread_id/selected_score/confidence_gap/candidates_json/context_size`

## 二、Auto Impression Card 当前职责（主线记忆底座）
1. 从 Thread Router 提供的关系/上下文进行印象与知识证据写入。
2. 管理别称、实体、证据、信任状态等结构化数据。
3. 通过 outbox/sync 机制向 Neo4j 同步 MemoryNode/Trace/Entity 等图数据。
4. 提供图谱查询能力给上游（router/read path）。

### 关键运行数据库（只读）
- `/Users/lincoln/Git/AstrBot/data/plugin_data/astrbot_plugin_auto_impression_card/impressions.db`
- `/Users/lincoln/Git/AstrBot/data/plugin_data/astrbot_plugin_auto_impression_card/trust_audit.db`

### 推荐读取表（只读）
- `processing_state`
  - 核心字段：`scope/last_ts/last_id/last_table/state_json`
- `impression_evidence`
  - 核心字段：`group_id/user_id/item_type/item_text/archive_id/speaker_id/message_text/message_ts/evidence_confidence/target_certainty/meta_json`
- `entity_registry`
  - 核心字段：`group_id/entity_id/canonical_name/entity_type/status/confidence/support_count/oppose_count/updated_at`
- `graph_memory_outbox`
  - 核心字段：`event_id/payload_json/status/retry_count/last_error/next_retry_at/updated_at`
- `graphiti_event_outbox`
  - 核心字段：`event_key/group_id/source_name/payload_json/retry_count/last_error/next_retry_at/updated_at`
- `graph_memory_sync_state`
  - 核心字段：`key/value/updated_at`
- `graphiti_import_checkpoint`
  - 核心字段：`scope/last_created_at/last_id/updated_at`
- `trust_audit.db`：`trust_evidence/evidence_archive/impression_item_event`

## 三、Humee Backend 抓数策略（当前阶段）
- 只读策略：
  - 读取 Thread Writer / Thread Router / AIC 的 SQLite 运行库
  - 读取 AIC outbox/sync 状态监控 Neo4j 同步健康
- 禁止事项（当前阶段）：
  - 直接改写 Thread Router 决策表
  - 直接改写 AIC 主表
  - 直接写 Neo4j（绕过 AIC）
- 日志策略：
  - 仅用于排障补充（示例日志：`/Users/lincoln/Git/AstrBot/data/logs/astrbot.log`）
  - 不作为主数据源

## 四、交付时需明确给团队的边界
1. Humee 首期是观测系统，不参与主链路决策闭环。
2. 主线数据链保持：`Thread Writer -> Thread Router -> AIC -> Reply`。
3. 后续 Agent Team 接入以“提案+审批+受控执行”为核心，不可绕过审计链。

## 参考文件（绝对路径）
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_thread_router/README.md`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_thread_router/AGENTS.MD`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_thread_router/services/prompt_context_service.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_auto_impression_card/AGENTS.md`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_auto_impression_card/graph_sync_service.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_auto_impression_card/update_service.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_auto_impression_card/memory_observability.py`
- `/Users/lincoln/Git/AstrBot/data/plugin_data/astrbot_plugin_thread_archive/thread_archive.db`
- `/Users/lincoln/Git/AstrBot/data/plugin_data/astrbot_plugin_thread_archive/llm_trace.db`
- `/Users/lincoln/Git/AstrBot/data/plugin_data/astrbot_plugin_thread_router/thread_router.db`
- `/Users/lincoln/Git/AstrBot/data/plugin_data/astrbot_plugin_thread_router/thread_router_trace.db`
- `/Users/lincoln/Git/AstrBot/data/plugin_data/astrbot_plugin_auto_impression_card/impressions.db`
- `/Users/lincoln/Git/AstrBot/data/plugin_data/astrbot_plugin_auto_impression_card/trust_audit.db`
