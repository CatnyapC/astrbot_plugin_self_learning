# Module 04 - Frontend Dashboard (First App Module)

## 目标
把 Dashboard 作为“平台首个小应用”落地在 macOS 风格 UI 中，并遵循后续可扩展到更多应用（人格管理、风格学习、黑话等）的壳层机制。
该平台产品名统一为 `Humee Backend`（控制台标题可用 `Humee Console`）。

## 页面分层（已定）
1. Dashboard 首层：仅展示聚合信息与群级入口。
2. Group Detail Window（二级窗口）：点击群卡片打开，展示该群详细流。

## 首层菜单约束（已定）
- Dashboard 首层不展示：
  - 实时决策流列表
  - Trace 详情弹窗
- 上述内容统一移入 Group Detail Window。

## 最小 API（前端依赖）
1. `GET /api/apps`（获取应用清单）
2. `GET /api/ops/overview`
3. `GET /api/ops/token_usage`
4. `GET /api/ops/cursors`
5. `GET /api/ops/health`
6. `GET /api/ops/group/{group_id}/messages`
7. `GET /api/ops/group/{group_id}/decisions`
8. `GET /api/ops/group/{group_id}/trace/{trace_id}`
9. `GET /api/ops/group/{group_id}/replies`

## 页面最小字段定义

### 顶部 KPI
- `total_tokens_1h` (number)
- `need_reply_rate_1h` (number, 0-1)
- `active_groups_1h` (number)
- `avg_decision_latency_ms_1h` (number)

### 群级卡片
- `group_id` (string)
- `token_total` (number)
- `thread_router_cursor` (string/number)
- `auto_impression_cursor` (string/number)
- `decision_last_need_reply` (boolean)
- `decision_last_ts` (number)
- `open_group_window` (action): 打开群详情窗口

### Group Detail - 消息流
- `archive_id` (number)
- `raw_id` (string, optional)
- `sender_id` (string)
- `message` (string)
- `ts` (number)
- `message_type` (string)
- `reply_to_archive_id` (string/number, optional)

### Group Detail - 决策流列表
- `id` (number)
- `trace_id` (string)
- `need_reply` (boolean)
- `case_name` (string)
- `reason` (string)
- `confidence` (number)
- `created_at` (number)

### Group Detail - Trace 详情弹窗
- `trace_id` (string)
- `decision` (object)
- `prompt_steps` (array)
- `token_usage` (array)

### Group Detail - 最终回复
- `reply_archive_id` (number)
- `reply_text` (string)
- `reply_ts` (number)
- `source` (string): `thread_archive` | `llm_trace`

## 前端实现约束（最简维护）
- 使用现有 `window.MacOSApi` 封装
- 初版使用轮询（2-5 秒）而非 WebSocket
- Dashboard 独立应用文件，注册到 app model（先不破坏现有壳层）
- Group Detail 使用独立窗口组件（建议 `GroupOpsWindow`），由群卡片触发打开
- 图表统一 ECharts

## 后续多应用约定
- 每个新应用一个独立 `apps/*.js` 文件
- app manifest 中配置 `app_id/component/title/order`
- 公共组件与 API 封装不复制，仅复用
- 优先新增 `DecisionReviewApp`（HITL 审批模块），交互模式参考 `PersonaReview`

## 自学习插件参考文件（绝对路径）
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/html/macos.html`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/js/macos/main.js`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/js/macos/app-model.js`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/js/macos/api.js`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/js/macos/apps/Dashboard.js`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/js/macos/apps/PerformanceMonitor.js`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/js/macos/apps/PersonaManagement.js`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/js/macos/apps/StyleLearning.js`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/js/macos/apps/JargonLearning.js`
