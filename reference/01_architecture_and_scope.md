# Module 01 - Architecture and Scope

## 目标
在不引入新框架的前提下，复用 `self_learning` 当前技术栈（Quart + Vue + ECharts）建设一个运维观测平台，满足：
- **独立运行**（不作为 AstrBot 插件生命周期的一部分）
- **多应用分块化**（Dashboard 为第一个应用）
- **统一命名**（产品名 `Humee Backend`）
- **明确对接边界**（仅对接 thread router / auto impression card / thread writer）

首期 Dashboard 监控范围：
- token 用量
- thread router catchup cursor
- auto impression card cursor
- thread router case 决策（是否回复）
- need-reply 时 prompt 构建链路（auto memory / prefetch / assembly）

## 架构原则
1. Standalone First: 服务进程独立启动，独立配置，独立日志。
2. App Shell + Apps: 先建设管理端壳层，再加载具体应用模块。
3. API Contract First: 先锁接口，再开发前后端。
4. Keep It Simple: 初版优先轮询，减少实时推送复杂度。
5. Data by DB: 主数据链路采用“读库 + Outbox”，日志仅排障。

## 对接范围（必须）
- 运行时只对接三插件：`thread router`、`auto impression card`、`thread writer`。
- `thread writer` 在当前仓库对应目录：`astrbot_plugin_thread_archive`。
- `self_learning` 仅作为 UI/工程组织参考，不参与运行时数据对接。

## 命名规范
- 产品名：`Humee Backend`
- 进程/包名：`humee-backend`
- 控制台标题：`Humee Console`
- 首个应用：`Dashboard`

## 最小 API（架构级）
1. `GET /api/apps`
用途：返回前端可加载应用列表（Dashboard 等）。

2. `GET /api/ops/overview`
用途：Dashboard 首屏聚合。

3. `GET /api/ops/health`
用途：全局健康状态。

4. `GET /api/ops/sync_status`
用途：查看 Outbox 消费位点与延迟。

## 字段定义（架构级）
### AppManifest
- `app_id` (string, required)
- `title` (string, required)
- `component` (string, required)
- `enabled` (boolean, required)
- `order` (number, required)

### OverviewResponse
- `ts` (number, required)
- `window_sec` (number, required)
- `group_count` (number, required)
- `hot_groups` (array, required)

### GroupSummary
- `group_id` (string, required)
- `group_name` (string, optional)
- `token_total` (number, required)
- `thread_router_cursor` (string/number, optional)
- `auto_impression_cursor` (string/number, optional)
- `latest_decision_need_reply` (boolean, optional)
- `latest_decision_ts` (number, optional)

## 目录建议（独立服务形态）
- `server/app.py`
- `server/workers/outbox_consumer.py`
- `server/blueprints/apps.py`
- `server/blueprints/ops_monitor.py`
- `server/services/ops_monitor_service.py`
- `server/services/app_registry_service.py`
- `server/services/outbox_sync_service.py`
- `server/repositories/ops_monitor_repository.py`
- `server/models/orm/ops_monitor.py`
- `web/static/js/macos/apps/DashboardApp.js`

## 自学习插件参考文件（绝对路径）
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/app.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/server.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/dependencies.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/blueprints/__init__.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/middleware/auth.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/utils/response.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/js/macos/app-model.js`
