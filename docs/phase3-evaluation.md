# Phase 3 offline evaluation / 第三阶段离线评估

Run from `services/api` / 在 `services/api` 目录运行：

```powershell
.\.venv\Scripts\python -m app.domain.evaluation
```

Fixture: `app/domain/fixtures/evaluation_v1.json` (five songs, two cases, two results per case).
No provider network or paid API is used. All ties have stable ordering.

| Metric | Definition / 定义 | v1 result |
| --- | --- | ---: |
| Relevance | Mean precision@2 against case labels / 对标签的平均准确率 | 1.0 |
| Personalization effect | Mean preferred-song rank improvement versus empty profile / 偏好歌曲平均名次提升 | 1.0 |
| Diversity | Mean unique artist, provider and genre fractions / 歌手、来源、风格多样性均值 | 0.8333 |
| Coverage | Unique recommended songs divided by fixture catalog / 推荐覆盖率 | 0.8 |

These numbers are regression signals for this small fixture; they do not estimate production
quality. / 这些数字仅供固定小样本回归，不代表线上效果。

Phase 6 release rerun, 2026-09-30: the same `evaluation_v1` output was reproduced; neither the
fixture nor ranking weights were changed. CI runs `python -m app.domain.evaluation` on every push/PR.
The evaluator's regression test checks all four metrics; separate Agent tests cover tool selection,
not a claimed tool-accuracy benchmark. No live latency/throughput or model-quality measurements
are included. / 第六阶段复测结果一致，不改算法或样本，不加入虚构线上指标。
