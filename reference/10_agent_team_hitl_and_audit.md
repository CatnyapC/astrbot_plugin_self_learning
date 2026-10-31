# Module 10 - Agent Team Integration, HITL, and Auditability

## 目标
定义 Humee Backend 后续如何接入旁路 `OpenClaw Agent Team`，并与 AIC/Neo4j 协作，保证：
- 不阻塞主线快流
- 所有改动可审计
- 执行路径 deterministic

## 旁路方案输入（来源）
- `/Users/lincoln/.gemini/antigravity/brain/89afc2ca-e790-4b4a-b5da-3fe116665ead/implementation_plan.md.resolved`

## 一、协作原则
1. 双轨制不变：
   - Fast Path：`Thread Writer -> Thread Router -> AIC -> Reply`
   - Slow Path：`Agent Team` 仅做异步提案/研究/整理
2. 当前阶段（已确认）：Humee 仅做读与审阅，不做干预性写入。
3. 后续写入必须经过 HITL 最终拍板，且落审计记录。
4. 对接范围仅限三插件（thread writer / thread router / AIC）；`self_learning` 仅作参考。

## 二、与 AIC/Neo4j 的配合方式（关键）
- 禁止：Humee/Agent 直接写 Neo4j 主图。
- 推荐：
  1) Agent 产出“变更提案”（proposal）
  2) 人工审批（approve/reject/modify+approve）
  3) 由受控执行器调用 AIC 公开入口或写入 AIC outbox 统一执行
  4) AIC 负责最终图同步与一致性处理
- 结果：避免多写入口造成图谱分叉与审计断裂。

## 三、HITL 决策应用模块（参考 PersonaReview）
- 模块定位：Humee 第二个应用（Dashboard 之后）
- 职责：
  - 展示 Agent 提案、影响范围、风险等级
  - 支持审批动作：`approve / reject / modify_then_approve`
  - 记录审批人、审批意见、审批时间、审批前后 diff
- 参考实现（self_learning 人格审查）：
  - `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/blueprints/persona_reviews.py`
  - `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/services/persona_review_service.py`
  - `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/js/macos/apps/PersonaReview.js`

## 四、最小数据模型（Humee 侧）

### `agent_proposals`
- `proposal_id` (PK)
- `source_agent` (`researcher/custodian/...`)
- `proposal_type` (`neo4j_merge/neo4j_reclass/config_update/...`)
- `target_scope` (group/entity/global)
- `payload_json` (提案内容)
- `input_snapshot_hash` (用于复现)
- `status` (`pending_review/approved/rejected/executed/failed`)
- `created_at/updated_at`

### `agent_reviews`
- `id` (PK)
- `proposal_id`
- `reviewer_id`
- `action` (`approve/reject/modify_then_approve`)
- `comment`
- `modified_payload_json` (可空)
- `created_at`

### `agent_execution_jobs`
- `job_id` (PK)
- `proposal_id`
- `idempotency_key` (唯一)
- `executor` (`aic_outbox_executor` 等)
- `status` (`queued/running/success/failed`)
- `result_json`
- `created_at/updated_at`

### `agent_audit_events`
- `id` (PK)
- `event_type` (`proposal_created/reviewed/execution_started/execution_finished/...`)
- `ref_id` (`proposal_id/job_id`)
- `actor`
- `payload_json`
- `created_at`

## 五、deterministic 控制点
1. 固化输入：每个提案保存 `input_snapshot_hash` 与来源证据 ID。
2. 固化执行：执行作业使用 `idempotency_key` 防重放。
3. 固化版本：记录 `policy_version/prompt_version/tool_version`。
4. 固化顺序：审批前禁止执行；审批后仅允许单一执行器落库。
5. 固化回溯：任意图变更都可追溯到 `proposal -> review -> job -> audit_event`。

## 六、接口建议（后续阶段）
- `GET /api/agent/proposals?status=pending_review`
- `GET /api/agent/proposals/{proposal_id}`
- `POST /api/agent/proposals/{proposal_id}/review`
- `POST /api/agent/proposals/{proposal_id}/execute`（仅 approved）
- `GET /api/agent/jobs/{job_id}`
- `GET /api/agent/audit?proposal_id=...`

## 七、阶段边界
- Phase A（现在）：只读观测 + Dashboard
- Phase B：Agent 提案展示 + HITL 审批（仍不执行写入）
- Phase C：审批后受控执行（默认关闭，灰度开启）

## 参考文件（绝对路径）
- `/Users/lincoln/.gemini/antigravity/brain/89afc2ca-e790-4b4a-b5da-3fe116665ead/implementation_plan.md.resolved`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_auto_impression_card/AGENTS.md`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_auto_impression_card/graph_sync_service.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_auto_impression_card/update_service.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_thread_router/AGENTS.MD`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/blueprints/persona_reviews.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/services/persona_review_service.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/js/macos/apps/PersonaReview.js`
