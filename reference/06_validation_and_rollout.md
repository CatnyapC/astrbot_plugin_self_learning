# Module 06 - Validation and Rollout

## 目标
保证新工具上线后可持续维护：接口可回归、性能可观测、故障可定位。

## 最小 API（验收检查）
1. `GET /api/ops/health`
- 用于 smoke test / 页面状态灯。

2. `GET /api/ops/overview`
- 用于端到端可用性验证。

3. `GET /api/ops/decisions?group_id=...&limit=20`
- 用于验证实时数据链路是否正常。

## 字段定义（验收视角）

### HealthResponse
- `overall` (string): `healthy | degraded | unhealthy`
- `checks` (object)
- `timestamp` (number)

### SmokeCheckResult
- `api_name` (string)
- `status_code` (number)
- `ok` (boolean)
- `latency_ms` (number)
- `error` (string, optional)

## 最小测试清单
- 鉴权：未登录访问 `ops` 路由返回 401
- 正常：有数据群组能返回 overview + chart 数据
- 边界：空群组、无决策记录、无 prompt trace 时页面不报错
- 性能：5 秒轮询下页面无明显卡顿，接口 P95 可接受
- UI 分层：Dashboard 首层不出现“实时决策流列表/Trace 详情”；点击群卡可打开群详情窗口
- 群窗口完整性：同一群可同时看到消息流、决策流、trace 详情、最终回复
- 只读保障（Phase A）：所有会导致写库的接口默认关闭或返回拒绝
- 一致性：`thread_router` 与 `AIC` 游标读数无倒退、无跨表口径冲突
- 审计性（Phase B/C）：任一审批执行都能追溯 `proposal -> review -> job -> audit_event`
- deterministic：同一 `idempotency_key` 重试不产生二次落库

## 自学习插件参考文件（绝对路径）
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/tests/integration/test_auth_blueprint.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/blueprints/auth.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/blueprints/monitoring.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/webui/services/metrics_service.py`
- `/Users/lincoln/Git/AstrBot/data/plugins/astrbot_plugin_self_learning/web_res/static/js/macos/api.js`
