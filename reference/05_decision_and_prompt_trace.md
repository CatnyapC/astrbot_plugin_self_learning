# Module 05 - Decision and Prompt Trace

## 目标
让“是否回复”的决策链路可追踪、可回放、可审计，重点覆盖：
- case 决策结果
- auto memory / prefetch / prompt assembly 各步骤
- 每步骤耗时与 token 估算

## 数据通路（独立管理端）
- 事件由插件侧写入 `ops_event_outbox`
- `Humee Backend` 通过事件位点增量消费并落地查询表
- 查询接口只读结构化表，不反查原始日志

## 最小 API（链路追踪）
1. `GET /api/ops/decisions?group_id=...&since_id=...`
2. `GET /api/ops/trace/{trace_id}`
3. `GET /api/ops/trace/{trace_id}/steps`（可选；也可合并到 trace 接口）

## 事件类型建议（Outbox）
- `router.decision.made`
- `prompt.trace.step.recorded`
- `token.usage.recorded`
- `cursor.updated`

## 字段定义（追踪对象）

### DecisionEvent
- `trace_id` (string, required)
- `group_id` (string, required)
- `thread_id` (string, optional)
- `message_id` (string, optional)
- `need_reply` (bool, required)
- `case_name` (string, optional)
- `reason` (text, optional)
- `confidence` (float, optional)
- `latency_ms` (float, optional)
- `created_at` (bigint, required)

### PromptTraceStep
- `trace_id` (string, required)
- `step_name` (string, required)
- `step_order` (int, required)
- `input_refs_json` (text, optional)
- `output_preview` (text, optional, 脱敏后)
- `token_estimate` (int, optional)
- `latency_ms` (float, optional)
- `created_at` (bigint, required)

## 脱敏与保留策略（MVP）
- `output_preview` 默认最大 300~500 字符
- 邮箱、手机号、密钥样式字段统一掩码
- 支持配置开关：是否记录 prompt 文本预览

## 自学习插件参考文件（绝对路径）
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/services/monitoring/instrumentation.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/services/monitoring/metrics.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/services/monitoring/collector.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/services/monitoring/health_checker.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/services/hooks/perf_tracker.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/blueprints/monitoring.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/js/macos/apps/PerformanceMonitor.js`
