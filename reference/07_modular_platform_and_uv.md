# Module 07 - Modular Platform and UV

## 目标
定义“独立运行 + 多应用平台 + uv 管理”的落地规范。

## 命名约定
- 产品名：`Humee Backend`
- 进程名：`humee-backend`
- 控制台：`Humee Console`
- 首个应用：`Dashboard`

## 独立运行要求
- 管理端必须作为独立服务启动，不挂靠 AstrBot 插件生命周期。
- 配置、日志、数据库连接独立管理。
- 能单独部署和重启，不影响 bot 主进程。

## 多应用平台要求
- 管理端包含 app shell（桌面、dock、窗口管理）。
- 业务以小应用形式注册到 app registry。
- Dashboard 是第一个应用，后续应用按同一协议接入。

## 数据接入要求
- 主通路：读库 + Outbox 事件消费。
- 日志仅用于排障与人工审计，不作为主查询数据源。
- 必须暴露同步状态（消费位点与 lag）用于运维观测。
- 对接范围固定为三插件：`thread writer`、`thread router`、`auto impression card`。
- `self_learning` 仅作为界面与流程参考实现，不参与运行时数据接入。

## 多应用演进要求
- `Dashboard` 之后优先落地 `Decision Review (HITL)` 应用模块。
- `Decision Review` 交互可参考 self_learning 的 `PersonaReview` 实现模式（列表 + 审批动作 + 历史回放）。

## 最小 API（平台）
1. `GET /api/apps`
- 返回应用清单。

2. `POST /api/apps/{app_id}/toggle`（可选）
- 启停某应用展示状态（后续阶段启用）。

## 字段定义

### AppManifest
- `app_id` (string, required)
- `title` (string, required)
- `component` (string, required)
- `icon` (string, optional)
- `icon_bg` (string, optional)
- `enabled` (boolean, required)
- `order` (number, required)
- `version` (string, optional)

### AppListResponse
- `apps` (array[AppManifest], required)
- `timestamp` (number, required)

## UV 工作流（项目级约定）
- 依赖安装：`uv pip sync requirements.txt`
- 本地运行：`uv run python -m server.main`（示例）
- 测试运行：`uv run pytest`
- 依赖变更后：统一通过 `uv` 更新，不混用其他包管理命令

## 建议目录（独立项目）
- `pyproject.toml`
- `requirements.txt`
- `server/`
- `web/`
- `tests/`
- `reference/`

## 自学习插件参考文件（绝对路径）
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/requirements.txt`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/server.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/manager.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/js/macos/app-model.js`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/js/macos/main.js`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/html/macos.html`
