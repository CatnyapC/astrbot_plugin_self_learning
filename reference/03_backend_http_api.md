# Module 03 - Backend HTTP API

## 目标
定义独立管理端所需最小 HTTP API。优先支持 Dashboard（首应用），并预留多应用扩展。

## 数据接入方式
- `Humee Backend` 直接读取三插件结构化库表（thread writer / thread router / auto impression card），并消费 Outbox 增量事件。
- 不提供“解析日志生成主数据”的 HTTP 路径。

## 最小 API（平台级）
1. `GET /api/apps`
- 返回启用中的应用列表（Dashboard 先行）。

## 最小 API（Dashboard 业务）
1. `GET /api/ops/groups`
2. `GET /api/ops/overview?window_sec=3600`
3. `GET /api/ops/token_usage?group_id=xxx&from_ts=...&to_ts=...&bucket=5m`
4. `GET /api/ops/cursors?group_id=xxx`
5. `GET /api/ops/health`
6. `GET /api/ops/sync_status`

## 最小 API（Group Detail Window 业务）
1. `GET /api/ops/group/{group_id}/messages?from_ts=...&to_ts=...&limit=...`
2. `GET /api/ops/group/{group_id}/decisions?since_id=...&limit=...`
3. `GET /api/ops/group/{group_id}/trace/{trace_id}`
4. `GET /api/ops/group/{group_id}/replies?since_ts=...&limit=...`

注：Dashboard 首层不直接展示决策流/trace；上述接口用于二级群窗口。

## 后续 API（Agent Team + HITL，Phase B/C）
1. `GET /api/agent/proposals?status=pending_review`
2. `GET /api/agent/proposals/{proposal_id}`
3. `POST /api/agent/proposals/{proposal_id}/review`
4. `POST /api/agent/proposals/{proposal_id}/execute`（仅 approved）
5. `GET /api/agent/jobs/{job_id}`
6. `GET /api/agent/audit?proposal_id=...`

## 字段定义（响应）

### AppManifest
- `app_id` (string, required)
- `title` (string, required)
- `component` (string, required)
- `enabled` (boolean, required)
- `order` (number, required)

### DecisionsResponse.item
- `id` (number, required)
- `trace_id` (string, required)
- `group_id` (string, required)
- `thread_id` (string, optional)
- `need_reply` (boolean, required)
- `case_name` (string, optional)
- `reason` (string, optional)
- `confidence` (number, optional)
- `latency_ms` (number, optional)
- `created_at` (number, required)

### TraceDetailResponse
- `trace_id` (string, required)
- `group_id` (string, required)
- `decision` (object, required)
- `prompt_steps` (array, required)
- `token_usage` (array, optional)

### GroupMessageResponse.item
- `archive_id` (number, required)
- `sender_id` (string, required)
- `message` (string, required)
- `ts` (number, required)
- `message_type` (string, required)
- `reply_to_archive_id` (string/number, optional)

### GroupReplyResponse.item
- `reply_archive_id` (number, required)
- `reply_text` (string, required)
- `reply_ts` (number, required)
- `source` (string, required): `thread_archive` | `llm_trace`

### SyncStatusResponse
- `consumer_name` (string, required)
- `last_event_id` (number, required)
- `latest_outbox_id` (number, required)
- `lag_events` (number, required)
- `last_sync_ts` (number, required)

### AgentProposalResponse
- `proposal_id` (string, required)
- `source_agent` (string, required)
- `proposal_type` (string, required)
- `status` (string, required)
- `risk_level` (string, optional)
- `created_at` (number, required)

### AgentReviewRequest
- `action` (string, required): `approve/reject/modify_then_approve`
- `comment` (string, optional)
- `modified_payload_json` (object, optional)

## 鉴权与返回风格
- 统一走 session/token 鉴权中间件（与现有 `require_auth` 语义一致）
- 错误统一 `error_response(...)`
- 成功统一 `jsonify(...)` 或 `success_response(...)`
- Phase A 约束：不暴露会触发写入的执行接口，或接口默认返回只读模式错误。

## 自学习插件参考文件（绝对路径）
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/blueprints/metrics.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/blueprints/monitoring.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/blueprints/social.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/services/metrics_service.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/services/social_service.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/middleware/auth.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/utils/response.py`
