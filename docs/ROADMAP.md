# Delivery Roadmap / 交付路线图

The authoritative checklist is [TODO](../TODO.md); the phase definitions and evidence are in
[PROJECT_PLAN](../PROJECT_PLAN.md). This index uses the same 0–6 phase numbering.
权威清单和验证证据分别见 TODO 与 PROJECT_PLAN，阶段编号保持一致。

| Phase | Delivered / 交付 |
| --- | --- |
| 0 | Legacy audit, shared context, architecture and ADRs / 旧版审查 |
| 1 | FastAPI/Next foundation, Compose, typed contracts and migrations / 工程基础 |
| 2 | Canonical catalog and bounded provider adapters / 统一模型和来源适配 |
| 3 | Deterministic ranking, feedback/profile, embeddings and fixed evaluation / 推荐与评估 |
| 4 | Product client and accessible recommendation/feedback states / 产品页面 |
| 5 | One bounded Agent, memory, RAG, SSE and MCP-style HTTP façade / 助手与知识 |
| 6 | Correlated JSON telemetry, CI, standard MCP stdio, release docs and startup checks / 最后工程阶段 |

Author-host Docker clean start was not executed because Docker is absent. A CI clean-start job
provides a separate verification path. Real-model quality and broad provider reliability are not
certified by offline tests. / 本机容器未实机执行，CI 可独立验收；不把离线测试当外部服务效果验证。

Future directions, not started / 未来方向（未实施）：larger verified catalog and real-user evaluation,
authentication and conversation retention/deletion, useful Redis caching/rate limits, remote MCP
authorization, and live-model/provider compatibility. No further engineering phase starts automatically.
