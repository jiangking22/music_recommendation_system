# Five-minute demo / 五分钟演示

Use the target Compose setup in [DEPLOYMENT](DEPLOYMENT.md). Set `ENABLE_MUSIC_PROVIDERS=false`,
`LLM_PROVIDER=local` and leave `LLM_API_KEY` empty for a reproducible no-business-network walkthrough.
Image/package downloads still require network on first build. No real-model or music-provider
quality is being demonstrated in this mode. / 用固定曲库演示工程链路，不把离线样本当线上质量。

## Recommendation flow / 推荐与反馈

1. Open `http://localhost:3000`; enter **calm jazz**, select **3**, press **Find music**.
   Blue Window appears first with a new device's empty profile. Cards expose deterministic score
   factors and fixture provenance. / 空画像首曲为 Blue Window，查看理由和来源。
2. Like the first track. The API upserts the device rating, recomputes affinities and vectors,
   and the preference panel refreshes. / 喜欢后画像与向量持久化。
3. Choose **Refresh recommendations**. Compare score factors before/after; personalization may
   change scores without changing the first title. / 对比偏好分数，不要求每次第一名都改变。
4. Reload the browser: the device identifier remains in localStorage and profile loads from the
   database. Clearing browser storage creates a new profile link. / 刷新保留偏好，清空存储则失去链接。
5. If enabling live sources, observe canonical metadata and a partial-source notice when a
   provider fails. Their current availability is independent of fixture tests. / 外网来源只作独立演示。

## Agent flow / 助手演示

| Prompt / 输入 | Expected local flow / 本地预期 |
| --- | --- |
| 推荐适合学习的歌 / Recommend songs for study | profile → recommend_tracks(calm jazz) → knowledge → explanation; same recommender order |
| 再来几首 / More songs | reuse current conversation's last seed; no arbitrary replanning |
| 介绍周杰伦 | knowledge retrieval only; citations to fixed artist document |
| 爵士乐有什么特点 / Tell me about jazz | lexical-guarded knowledge answer |
| 介绍一个知识库没有的冷门艺术家 | no evidence: local assistant says the fixture lacks relevant material |

Open `/agent`, submit the first prompt and inspect **分析需求 → 查询偏好 → 调用工具 → 返回结果**,
used tool names, canonical results, factor explanations and citations. Continue with **再来几首**.
The server remembers six turns; page refresh starts a new UI conversation because there is no
history loader. / 会话持久化，但刷新页面会开始新会话；不宣称已实现历史会话 UI。

No Key uses the local rule router. A configured real-model failure returns an explicit safe
error. JSON/SSE/tool-selection tests validate the adapter contract using mocks; no live LLM result
or benchmark is claimed. / 真实模型未实测，不能把 mock 成功当真实效果。

## MCP flow / 标准协议演示

Install `.[dev,mcp]`; configure the client to run `python -m app.mcp.server --offline` from
`services/api`. Discover `music_search` and `recommend_tracks`. Search `{query: "jazz", limit: 2}`;
then recommend `{seed: "calm jazz", limit: 3}`. The server is read-only, does not accept device
profile overrides, and returns canonical structured content. / 只读工具复用业务层，不跨设备访问画像。

The test `tests/test_mcp_transport.py` launches a real subprocess, initializes an official SDK
client, lists schemas, calls both tools and rejects excessive limits and unknown tools. The old
`/v1/mcp` HTTP routes remain an MCP-style façade, not a standard HTTP transport.

## Evaluation summary / 评估说明

From `services/api`, `python -m app.domain.evaluation` prints:

```json
{"cases":2,"coverage":0.8,"diversity":0.8333,"personalization_effect":1.0,"relevance":1.0,"version":"evaluation_v1"}
```

[Definitions](phase3-evaluation.md): five songs, two labeled cases, precision@2, preferred-song rank
lift, attribute diversity and unique catalog coverage. Repeatable regression fixture, not a
real-user benchmark. No latency, throughput or live-model accuracy benchmark is claimed.

## Interview talking points / 面试说明

- Why deterministic rank? Explicit factors and fixed regression evaluation; Agent cannot bypass it.
  / 为什么保留传统排序：策略可解释、可验证。
- Why small embeddings/RAG? No downloads or keys; acknowledge collision/semantic limits.
  / 小向量降低运行成本，明确语义能力边界。
- Why anonymous linkage? Demonstrates durable feedback with limited product scope; it is not auth.
  / 匿名标识缩小产品范围，不能保证安全身份隔离。
- Why stdio MCP and JSON logs? Real interoperability and diagnosis with minimal operational stack.
  / 用最小运行成本展示标准工具调用与问题定位。

Use [screenshot guidance](screenshots/README.md) to capture actual runtime output; do not fabricate
screenshots, benchmark numbers or CI status.
