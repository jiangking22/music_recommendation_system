# Browser screenshots / 真实页面截图

Captured on 2026-10-02 from the existing Next.js production build and FastAPI service at
`http://localhost:3000` and `http://localhost:8000`, using the Codex in-app browser's default
1264px-wide viewport and full-page capture. Browser JPEG captures were re-encoded as PNG with
identical decoded pixels; no UI, text, or results were composited or altered.

截图来自现有前后端真实运行页面，使用默认 1264px 宽视口全页拍摄；仅转为 PNG 格式，未修改页面或截图内容。

## Capture environment / 拍摄环境

`ENABLE_MUSIC_PROVIDERS=false`, `LLM_PROVIDER=local`, and an empty `LLM_API_KEY` select the
committed catalog and deterministic local router. This Windows host has no Docker. A temporary
SQLite test database was initialized with the existing SQLAlchemy metadata and `ingest_fixture`
helper; no API responses were mocked and no application code was changed. Redis/readiness,
PostgreSQL/pgvector, container startup, live providers and real LLMs were not verified by this capture.

使用离线固定曲库与本地规则助手，以及临时 SQLite 测试库和已有知识资料导入函数；未 mock API 或改动应用代码。
这不是完整 Compose 部署验收，也不证明真实音乐源或 LLM 效果。完整运行方式仍见 [DEPLOYMENT](../DEPLOYMENT.md)。

## Captured states / 截图状态

- [recommendations.png](recommendations.png): `calm jazz`, three results, empty profile, first
  recommendation's score factors expanded; Blue Window scores 3.16.
- [preferences.png](preferences.png): like Blue Window, then refresh recommendations; the profile
  shows Demo Quartet / Calm / Jazz and the saved like, with Blue Window scoring 6.16.
- [agent.png](agent.png): submit `推荐适合学习的歌` on `/agent` with that profile; local assistant,
  three fixture tracks, completed public tool statuses and knowledge citations.

按照 [DEMO](../DEMO.md) 的推荐、点赞、刷新与助手流程拍摄。图片只包含演示输入与 fixture 结果，
不含私密聊天、设备 ID、请求头或凭据；原有课程资料不作为本次发布素材。

Release audit on 2026-10-02 visually rechecked all three images against main `4c54239`.
Product code is unchanged since capture commit `1c76b33`; a fresh local HTTP smoke reproduced
the 3.16 → 6.16 recommendation scores and local Agent/citations with the same fixture setup.
No screenshot was modified or recaptured during release preparation.
发布准备已复核图片、链接与演示状态；本次未修改或重拍截图。
