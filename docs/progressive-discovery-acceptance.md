# Progressive assistant acceptance / 音乐助手渐进检索验收

Verified on the local Windows host on 2026-10-07 using the configured model and existing
iTunes/NetEase/QQ catalogs through the real Next.js authentication and SSE proxy.
No provider/model credentials were changed. This is local acceptance, not a production deployment.

| Request / 本轮需求 | Returned / 返回 | Expanded / 扩搜 | External operations / 外部调用 |
| --- | ---: | --- | ---: |
| 舒缓歌曲 | 5 / 5 | Yes | 13 |
| 带人声 | 5 / 5 | Yes | 5 |
| 偏华语 | 5 / 5 | Yes | 5 |
| 再来几首 | 5 / 5 | No; reused unseen candidates | 0 |

The two explicit refinements made fresh catalog calls. All displayed songs were unique within
each result; the final five excluded every previously displayed song in the conversation.
Model-assisted language/vocal/feel evidence appeared as labelled inference. The client showed
filtering, catalog expansion and recording verification as actually emitted by SSE.
Earlier runs also exercised partial results and the 45-second discovery deadline without padding.

两次增加条件均实际检索音乐平台；最后一轮候选充足，直接推荐未展示歌曲。推断有独立标识。
外部来源与模型判断具有不确定性，本次五首结果不代表每个请求都能凑满；不足时返回真实原因。

Automated checks: 351 API tests; 90 Web tests; Ruff and Python compile; ESLint and TypeScript;
production Web/API images and Web build; dependency audit policy; migration SQL and drift checks;
legacy help and isolated homepage HTTP 200. The existing dependency audit exception remains
development-only. The API test runner reports an existing Starlette/httpx deprecation warning.

Database safety: PostgreSQL custom-format backup outside the repository, restoration into a
separate database, then 0008→0009→0008→0009 and Alembic check in that copy. Live upgrade added
empty search_state to all three existing conversations, preserving old data. No live downgrade.

Browser acceptance: isolated Edge via bundled Playwright, 1440×1000 desktop and 390×844 mobile,
no horizontal overflow or page exceptions; input remained usable after Stop. Browser/computer
plugin initialization failed with a missing kernel-assets path, so the isolated browser supplied
real runtime verification. Screenshots/test credentials remain outside source control; QA rows
are removed after verification.
Replaying the captured real result verified that repeated inference labels render once. Browser
console inspection found the existing missing `/favicon.ico` (404); no other console warning/error
or page exception occurred. The unrelated favicon remains outside this assistant change.

Brave is **not configured** on this host. UI reports “网页搜索未配置”; music catalog expansion
continues. Canonical snippet parsing, identity verification, rejected mismatched recording IDs,
missing key, failure, cancellation, early stop, deadline and operation caps pass mocked tests.
Live Brave search is unverified and requires BRAVE_SEARCH_API_KEY configured outside source
control, followed by recreating the API service. Native model search remains separately unavailable.

Brave 真实联网验收仍待环境密钥；不要在对话或仓库中填写密钥。现有音乐平台检索独立可用。
