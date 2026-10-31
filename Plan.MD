# Humee Backend Plan (Standalone + UV + Modular Apps)

## 总目标
建设一个**独立运行**的网页管理端（不再作为 AstrBot 插件生命周期的一部分），并保持 self_learning 现有技术栈风格（仅参考，不对接），先交付 Dashboard，再逐步扩展为多应用管理平台。

## 命名约定
- 产品名：`Humee Backend`
- 服务进程名：`humee-backend`
- Web 控制台标题：`Humee Console`
- 本文内若出现“管理端/控制台”，均指 `Humee Backend`

## 强约束（本计划必须满足）
- 独立运行：Web 管理端作为独立服务进程启动/停止，不依赖插件 on_load/on_unload。
- 技术栈延续：后端 Quart + Hypercorn；前端 Vue + Vuex + ECharts（macOS 风格 UI）。
- 依赖管理：继续由 `uv` 统一管理项目依赖与运行命令。
- 产品形态：采用“小应用分块化”架构，Dashboard 是第一个应用模块，不是唯一模块。
- 系统原则：主链路与旁路解耦，所有旁路变更必须可审计、可回放、可追责。

## 对接范围（硬约束）
- `Humee Backend` 运行时**仅对接以下三个插件**：
  1. `thread router`
  2. `auto impression card`
  3. `thread writer`
- 术语映射说明：当前代码库中 `thread writer` 对应的消息归档插件目录是 `astrbot_plugin_thread_archive`。
- `self_learning` 当前仅作为实现参考插件，**不在 Humee Backend 运行时对接范围内**。

## 数据接入决策（已确认）
- 主路径：**读库 + Outbox 事件表**（推荐且默认）
- 辅助路径：必要时直读现有聚合表/快照表
- 日志策略：日志仅用于排障与审计，不作为主业务数据源
- 目标效果：既能做历史查询，也能做低延迟增量刷新（轮询消费 Outbox）
- 当前阶段：**只读接入（无干预性写入）**。

## 需求拆解（当前首期）
1. 每群 token 用量监控（实时 + 趋势）
2. thread router catchup cursor 位置监控
3. auto impression card cursor 位置监控
4. 每群 thread router case 决策流（是否需要回复）
5. need-reply 场景下 auto memory / prefetch / prompt 构建链路追踪
6. 群级卡片可点击打开独立群窗口，查看消息流/决策流/trace/最终回复

## 当前系统上下文（需交付团队）
- Thread Writer 当前职责：群聊消息落盘归档（`thread_archive.db`），为 Router/AIC 提供历史源。
- Thread Router 当前职责：关系优先路由、need_reply 决策、catchup 追游标、trace 记录。
- Auto Impression Card 当前职责：证据写入、印象/别称/实体聚合、Neo4j 同步与 outbox。
- Humee Backend 首期职责：只读观测，不影响主线决策与写入路径。
- 未来扩展：接入旁路 `OpenClaw Agent Team` 的决策与配置应用，并通过 HITL 模块审批后再执行。

## 平台化范围（中期）
- 多应用壳层：
  - Dashboard（首个应用）
  - 后续应用（如 Persona 管理、风格学习、黑话、运行诊断等）
- 应用注册机制：前后端都存在 app registry，支持按配置启停显示。
- 公共能力复用：鉴权、API 封装、图表组件、时间筛选、群选择器。

## UV 管理规范
- 依赖安装/同步：使用 `uv`（如 `uv pip sync requirements.txt`）
- 运行：使用 `uv run` 启动服务
- 测试：使用 `uv run pytest`
- 约定：不引入额外包管理工具链，保持一套 `uv` 工作流

## 参考模块与阅读时机

### Stage 0 - 独立化与模块化边界（先读）
- [Architecture and Scope](./reference/01_architecture_and_scope.md)
- [Modular Platform and UV](./reference/07_modular_platform_and_uv.md)
- [Current AstrBot Runtime (Thread Writer + Thread Router + AIC)](./reference/09_current_runtime_thread_router_aic.md)
- 阅读时机：需求冻结前、目录与运行方式定稿前。

### Stage 1 - 数据模型与采集（第二步读）
- [Data Collection and Storage](./reference/02_data_collection_and_storage.md)
- [Data Access Strategy](./reference/08_data_access_strategy.md)
- [Decision and Prompt Trace](./reference/05_decision_and_prompt_trace.md)
- 阅读时机：建表/ORM/repository 与埋点接入前。

### Stage 2 - 后端 API 合同（第三步读）
- [Backend HTTP API](./reference/03_backend_http_api.md)
- 阅读时机：开始写 `blueprints/services` 前，先锁接口。

### Stage 3 - Dashboard 首应用（第四步读）
- [Frontend Dashboard](./reference/04_frontend_dashboard.md)
- 阅读时机：开始开发 Dashboard 首层与群详情窗口时。

### Stage 4 - 旁路 Agent Team 与 HITL（第五步读）
- [Agent Team Integration and HITL](./reference/10_agent_team_hitl_and_audit.md)
- 阅读时机：准备接入 OpenClaw Agent Team 决策/配置模块前。

### Stage 5 - 验收与发布（最后读）
- [Validation and Rollout](./reference/06_validation_and_rollout.md)
- 阅读时机：联调完成后、上线前。

## 里程碑（按交付顺序）
1. 完成独立服务骨架与 app registry（无业务数据也可启动）
2. 接入三插件数据（thread writer / thread router / AIC，读库 + Outbox）
3. 上线 Dashboard（首个应用）
4. 验证实时决策流与 trace 回放稳定性
5. 上线「决策审阅/HITL」应用模块（参考 PersonaReview 交互）
6. 接入 OpenClaw Agent Team 的决策/配置流（先提案、后审批）
7. 在审批闭环稳定后再开启受控写入（默认关闭）

## MVP 交付边界（仅 Dashboard）
- 做：
  - `ops` 数据采集与查询（含 Outbox 增量消费）
  - Dashboard 首层（KPI + 群级卡片 + 健康状态）与轮询刷新
  - 群详情独立窗口（消息流 + 决策流 + trace 详情 + 最终回复）
- 不做（后续迭代）：
  - WebSocket 实时流
  - Agent Team 直接写库
  - 未审批自动写入 Neo4j

## 首层 UI 约束（已定）
- Dashboard 首层菜单不展示“实时决策流列表”和“Trace 详情弹窗”。
- 上述两项仅在“群详情窗口”中展示。

## 后续阶段边界（Agent Team）
- 做：
  - Agent 提案可视化（决策、配置、图谱变更建议）
  - Human-in-the-loop 审批流（批准/修改后批准/驳回）
  - 审批与执行审计链
- 不做：
  - 无审批自动执行高风险图谱写入
  - 绕过 AIC 既有同步/审计路径的“旁路直写”

## 当前状态
- 已完成计划与 reference 文档更新。
- 按你的要求，仍未开始功能代码开发。
