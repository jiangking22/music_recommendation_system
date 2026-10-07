# Architecture Decision Records / 架构决策记录

## ADR-037: Fixed conversation viewport with reader-controlled following

**Status:** Accepted (approved fixed-chat plan)
**Date:** 2026-10-07

Bound the entire assistant panel using viewport-based desktop/mobile clamps, with a fixed header
and composer around one scrolling message region. Welcome, pending, failure, fallback and stopped
states share that region so no state expands the panel. Sending follows the newest message;
responses follow only within 48px of the bottom, otherwise preserve reading position and offer
“回到最新”. Do not create separate scrollbars per answer or move external cards/references inside.

Keep displayed turns for the current page visit instead of trimming them when backend context
rolls forward. This client history is cleared on unmount/logout, never synchronized, and does not
expand the existing six-turn model context. Use VisualViewport resize and input focus to bound
the panel during mobile keyboard shrink; clean up listeners on unmount. No dependency, HTTP schema,
provider/ranking change, persistence migration or legacy-demo change.

聊天区固定高度、内部滚动；上翻阅读时不强制跟随。页面可见历史与服务端最近六轮上下文分别管理，
退出登录仍取消请求并清空页面；键盘缩小可用视口时调整面板，让输入和停止操作可达。

## ADR-036: Qualitative music interpretation without measurement boilerplate

**Status:** Accepted (explicit user correction; revises ADR-034/035 answer restrictions)
**Date:** 2026-10-07

Music chat may explain styles and familiar recordings' qualitative listening impressions from
model music knowledge, framed as interpretation rather than audio measurement or verified retrieval.
Precise BPM, verified instrumentation/version details and current facts still require evidence.
Unfamiliar recordings require identity clarification; catalog labels only support possible genre
tendencies. Separate chat prose rules from homepage factor-grounded JSON guidance. Remove the
repeated missing-measurements tool field and local explanation warning. Zero new tools means no
new search, not failed/empty discovery; cached explanations use canonical previous factors.

Interpretations never become ranking evidence, filters or a replacement order. No API, schema,
model budget, credential, search capability or migration change. Current six-turn memory remains.
允许定性曲风交流；精确事实仍须核对。模型解读不参与筛选排序，也不能伪装成实听、实测或联网结果。

## ADR-035: Verified native-search capability and explicit unavailability

**Status:** Accepted (approved assistant plan)
**Date:** 2026-10-07

Use only the configured model service for native-search verification. The authenticated
`GET /v1/agent/capabilities` and both chat responses expose typed `native_search` status;
unknown protocols remain unverified/unavailable rather than inferred from model names or prose.
No Brave key, new search service, generated URL citation or per-request probing is introduced.

The official DeepSeek Responses documentation states that built-in `web_search` tools are ignored.
A bounded real request using the configured model on 2026-10-07 produced no completed search
records with verifiable source annotations. Search therefore remains unavailable in the adapter
and UI. The manual content-free probe requires both completed search calls and safe HTTPS source
annotations; even a positive probe needs an explicit adapter integration before enabling search.
General music discussion and opt-in thinking remain available without search.

联网使用同一模型服务独立核验；当前真实探测未通过，页面明确显示“当前模型接口暂不支持联网检索”。
模型自行生成的链接不作为搜索证据。参考：[DeepSeek Responses API](https://api-docs.deepseek.com/guides/responses_api/)。

## ADR-034: Contextual dialogue and metadata-backed listening refinements

**Status:** Accepted (approved assistant plan; revises ADR-014/016)
**Date:** 2026-10-07

Allow 0–4 distinct validated calls: music discussion, one clarification and explanation of
previous results do not require a fresh recommendation. Store bounded canonical recommendation
factors and language/vocal constraints in existing account/session conversation JSON. Latest
corrections win; refinements preserve earlier constraints and explicit new listening requests
reset them. No migration, cross-session history or inferred durable preference writes.

Optional typed constraints run inside the deterministic core before diversity selection, using
only explicit catalog metadata. Unknown/conflicting metadata cannot satisfy a hard requirement;
names or language scripts cannot prove vocals, BPM or language. Existing score weights and
unconstrained outputs remain unchanged. Answers separate general concepts from verified song facts.

Live DeepSeek chat intermittently returned malformed JSON or extra fields despite JSON output
mode. Conversation prose therefore uses text mode, canonically wrapped as Answer at the adapter
and length/completion-validated by the core. Plans, identification and homepage guidance still
use strict JSON. No permissive JSON repair, retry loop or ranking output from model prose.

支持自然讨论与逐轮澄清，解释使用上一轮真实匹配因素；语言与人声条件只用明确曲库元数据，
缺资料不伪造符合条件的歌。聊天正文由适配器包装为类型化回答，工具计划仍严格校验。

## ADR-033: Manual assistant deep thinking with isolated budgets

**Status:** Accepted (approved assistant plan; revises ADR-021 for chat only)
**Date:** 2026-10-07

Expose optional strict `deep_thinking=false` on both chat transports. Only the official DeepSeek
adapter has a documented thinking mapping: enable thinking for chat plan and answer when requested,
with 8,192 tokens, 256 KiB response cap and 50-second model timeouts inside a 120-second turn.
Homepage calls retain non-thinking/1,200-token/10-second behavior. Local/unsupported providers
report actual mode; outages retain the existing labeled deterministic fallback. Reject truncated
or non-complete outputs even if their content happens to be valid JSON. Discard raw reasoning.

The page-local checkbox defaults off; Stop aborts the stream, permits retry and ignores late replies.
Extend browser/auth/proxy deadlines only for assistant chat. No ranking, authentication, credentials
or database schema change. Cancellation cannot roll back a synchronous memory commit already running.

对话支持手动思考，深度模式最多两分钟；识曲保持原配置，降级如实显示。不保存或输出原始思考，
截断回答不能充当成功结果。后续连续对话和联网状态仍按独立 TODO 顺序实施。

## ADR-032: Matching username and password length bounds

**Status:** Accepted (explicit user correction; supersedes ADR-031)
**Date:** 2026-10-06

Usernames and passwords now require 6–20 characters inclusive. Apply the same bounds in typed
authentication requests, web validation, bilingual hints and local password reset. Usernames keep
their ASCII letters/digits/underscore restriction and case-insensitive database uniqueness;
password length counts Unicode characters and preserves spaces. Existing database rows are retained;
new authentication input must satisfy the corrected policy. Hashing and session ownership are unchanged.

## ADR-031: User-requested password minimum

**Status:** Accepted (explicit user amendment to the account plan)
**Date:** 2026-10-06

Accept 7–128 Unicode characters for registration, login, password changes and administrator reset,
replacing the original 15-character minimum. Spaces and password-manager paste remain supported;
no composition rules are added. Usernames remain case-insensitively unique, backed by the existing
database constraint. Password hashing, session revocation and account ownership are unchanged.

## ADR-030: Specific development-only dependency audit exception

**Status:** Accepted (bounded release validation policy)
**Date:** 2026-10-06

The release audit found source-map-js GHSA-68fv-2mgg-jv7q in the existing Next/PostCSS tree;
update the lockfile from 1.2.1 to its patched 1.2.2 release without changing Next/React versions.
The existing ESLint glob tree has GHSA-vfj7-8cjw-p6xm, with no patched braces version available.
Allow only this exact advisory and its known five-package dependency chain, only where every
installed node is marked development-only in the lockfile. All other high/critical advisories,
any runtime occurrence and unavailable/malformed audits fail CI. The exception remains visible
in audit output and deployment docs; it is not a clean full-audit claim. Glob patterns come from
trusted repository tooling, not HTTP users. Revisit when upstream publishes a patch.

## ADR-029: Mandatory account login and portable music preferences

**Status:** Accepted (user-approved implementation plan)
**Date:** 2026-10-06

Username/password accounts replace anonymous linkage for target HTTP business access, superseding
ADR-003/013/015 on that boundary. FastAPI verifies Argon2id passwords and revocable PostgreSQL
sessions; cookies are HttpOnly/SameSite and Secure in production. Origin + CSRF checks protect
writes; Redis bounds registration/login. Next.js provides fixed same-origin API transport.

New account tables store feedback/profiles/vectors; no anonymous row is claimed. Latest feedback
wins, with serialized per-account profile rebuilds. Agent context is account/session isolated,
not portable history. Public recording knowledge and deterministic ranking are unchanged.
Local administrator CLI handles password resets and revokes sessions. No email, OAuth or admin UI.
Legacy runtime and local public-data stdio MCP remain independent. Deployment requires a database
backup and isolated migration/rollback checks. See `docs/specs/account-login.md` for acceptance.

Implementation boundary: the fixed Next proxy ignores client IP forwarding headers, so source
limits conservatively aggregate proxied clients; account limits remain independent. No untrusted
header may select a data owner or bypass a limiter. `X-Session-Id` is a non-secret stale-tab guard,
not an authentication credential. `/auth/me` includes expiry so the UI can clear content at expiry.
Vector reflection retains database dimensions, allowing Alembic to detect pgvector schema drift.

## ADR-028: Confirm every model-derived artist before recommendation

**Status:** Accepted; supersedes ADR-022's automatic recommendation after model identification
**Date:** 2026-10-06

Initial discovery now returns `requires_confirmation=true`, the real seed recording and its
verification reference, with no related recall or ranked items when a model supplied the artist.
The same confirmation component handles initial and rejected-candidate model suggestions. Catalog
presence verifies the recording only; the user must confirm that this is the artist they meant.
Explicit artist inputs, reviewed hints and theme behavior retain their existing contracts.

Users can reject even a successfully matched model artist and supply a different artist. The
manual resolver searches available platforms by default, optionally narrowed by platform/link,
without another model call or recommendation. A verified recording is selected explicitly before
discovery re-fetches its provider ID, remembers the confirmed result and runs deterministic ranking.
Editing manual inputs invalidates the previous recording choice, while retaining its search report.
No schema migration, new model configuration or scoring change is needed.

首次与补充识别中的模型歌手均需用户确认；“不是这位歌手，我来填写”隐藏原建议的确认动作，要求填写歌手，
重新联网核实后才允许确认推荐。沿用查询快照、取消与重复提交保护、来源报告、预算和成功记录规则；
模型猜测、被否定歌手或仅填写文本均不能写入已核实知识。

## ADR-027: Share bounded recording expansion and remember confirmed provider IDs

**Status:** Accepted; supersedes ADR-024/025/026 homepage search caps and no-persistence scope
**Date:** 2026-10-06

Use one request-local resolver for discovery, rejected-candidate verification and manual platform
or link recovery. Revalidate success memory, search common catalogs, then regional Apple and
MusicBrainz metadata. Optional Brave returns only clues for registered detail lookups. Keep Kugou
and Kuwo unavailable after failed live feasibility probes. Report exactly what ran and distinguish
budget/deadline/partial failure from a completed miss; never infer that a song does not exist.

Maintain 45 seconds/one 8-second model call, at most 24 external requests with four reserved for
related recall, and four global outbound slots. Sequential per-request calls stay below the two-source
concurrency ceiling. Manual recovery gets 30 seconds/six requests. Provider failures are isolated;
MusicBrainz shares a one-per-second limiter and is explicitly metadata-only.

Issue 30-minute PostgreSQL verification references and re-fetch the same platform ID on confirmation.
Only confirmed, freshly verified recordings enter durable success memory. Stale IDs continue through
expansion; homonyms remain separate. References and knowledge are public recording metadata, not
device authentication, private conversation memory, global authorship certification or model training.
Fixed adapter endpoints and validated HTTPS song-link IDs avoid arbitrary URL fetch/redirect execution.

新增迁移与解析接口是用户已批准的范围调整；原推荐器继续负责召回、评分与排序。具体契约、来源可用性、
配置与恢复流程见 [recording resolution](docs/recording-resolution.md)。旧请求与旧版演示继续兼容；
未配置 Brave 不进行网页搜索，未接入平台不冒充已检索。适配器稳定性和平台收录仍限制覆盖率。

## ADR-026: Enable domestic catalog coverage in the shared registry by default

**Status:** Accepted; supersedes the QQ opt-in default, retaining ADR-025 regional Apple fallback
**Date:** 2026-10-06

### Decision

Live queries for 宠爱 / TFBOYS missed the default Apple/NetEase recording, while the existing QQ
adapter returned track 102210521 with a real source link. Enable QQ by default in Settings, Compose
and `.env.example`; update this host's boolean switch without changing its credentials. Preserve
explicit `ENABLE_QQ_PROVIDER=false` and global offline mode. Reuse the same registry for initial
model discovery, rejection verification and confirmed/refresh recommendations, so a verified QQ
seed remains retrievable without a new source-selection API or parallel ranking policy. Display
canonical evidence links for all matched model suggestions.

### Consequences

One query can now invoke three bounded sequential adapters; the existing three-operation budget
permits at most nine upstream search calls. Four-second provider timeouts, 37-second cumulative
compute waiting, 45-second request deadline, concurrency and result caps remain unchanged. QQ's
public web endpoint remains `unverified` as an integration stability classification; a returned
recording is evidence of catalog presence, not a general service/rights/authorship guarantee.
No scraping, authentication workaround, dependency, migration or scoring-rule change is added.

默认开启已有 QQ 来源，修复《宠爱》的真实曲库缺口；保留用户关闭与全局离线。首次查询、确认和刷新共用同一
曲库集合，避免核实成功后再次丢失起点歌曲。失败仍按来源降级，不编造录音或永久保存原唱判断。

## ADR-025: Verify missing model suggestions in bounded regional online catalogs

**Status:** Accepted; extends ADR-024 catalog verification after the user's requested fallback
**Date:** 2026-10-06

### Decision

The default US Apple catalog omitted 晴天 / 周杰伦, while Taiwan and Hong Kong returned real
recordings. Use Apple's documented [Search API country parameter](https://performance-partners.apple.com/search-api)
for additional online verification. Reserve at least one of the existing three search operations:
at most two default artist/alias queries, followed by TW and, if budget remains, HK. Each lookup
retains bounded provider timeouts/results and the existing shared capacity/deadline. Clone the
registry per request, change only iTunes's country, retain other configured providers and offline
mode, and preserve shared US defaults. Abstain if no valid title/artist recording is found.

Expose nullable `verified_storefront` and a canonical provider evidence link for actual regional
Apple matches. Retain user confirmation, passing an optional allowlisted `seed_storefront` with
`seed_artist` to discovery. Revalidate the recording and recall/rank in that region; preserve the
selection through feedback refresh and clear it on input edits. Never manufacture IDs, trust model
URLs, scrape arbitrary web pages, or force unrelated songs into an unresolved recommendation.

### Consequences

Recording availability still does not certify original authorship. This closes the observed
storefront coverage gap, not every missing recording worldwide; alias searches can leave only TW
within the fixed budget. No new key, external search service, migration, knowledge base or ranking
policy is required. Source failures remain visible and all-source misses stay unverified.

默认曲库未匹配时增加有界官方地区联网核查；《晴天》在实际配置模型与浏览器中匹配台湾区录音，确认后返回五首
推荐。地区只影响请求内曲库，保留原有用户确认与重新核验步骤；单次实测不构成原唱识别准确率保证。

## ADR-024: Explicitly reject artist candidates and confirm model suggestions before recommendation

**Status:** Accepted; adds a user-triggered fallback to ADR-022 without changing initial discovery
**Date:** 2026-10-06

### Decision

Add “以上均没有 / None of the above” after ambiguous homepage artist choices and a dedicated
`POST /v1/recommendations/identify-original` contract. Send the original query and 1–5 rejected
title/artist summaries through the existing configured model once. Validate structure and song
title, exclude rejected artist identities using reviewed aliases, and verify via canonical providers
within three bounded queries. Reviewed spelling variants may improve catalog retrieval without
registering model-generated aliases. Share discovery's request semaphore, worker pool and deadlines.

Separate model suggestion from catalog recording presence. A matched suggestion requires explicit
user confirmation and a fresh `discover` call with `seed_artist` before deterministic recommendation.
Unmatched suggestions remain visible as unverified text with no synthetic Track or recommendation.
Unknown, repeated or unrelated suggestions abstain. Distinct safe errors allow manual retry; pending
lookups abort on new searches/unmount, and interface language changes do not cause a model call.

### Consequences

Catalog presence does not prove original authorship; the UI says so and retains model origin after
confirmation. Provider coverage may leave a correct model suggestion unverified. Rejected candidates
are request-scoped user input, not persistent music facts. No migration, durable authorship store,
ranking change, new model configuration or browser credential is needed. Content-free correlated
events expose status, timing and error codes without prompts, identities or credentials.

候选全部否定后仅调用一次已有模型；曲库匹配成功也必须先确认再推荐，未匹配时仅展示待核实建议。
原唱判断和录音存在性分开说明，不将模型输出写入永久知识库或改变确定性排序。

## ADR-023: Keep assistant recommendations available during model transport failures

**Status:** Accepted; refines ADR-014 model-failure behavior; homepage identification rules in ADR-022 remain unchanged
**Date:** 2026-10-06

The shared model adapter supplies Python's system-trust SSL context to HTTPX, retaining required
certificate and hostname verification. HTTPX proxy environment discovery remains disabled.
This fixes the observed certifi/system trust mismatch without disabling TLS verification or
automatically trusting a certificate received from the network. See [HTTPX SSL configuration](https://www.python-httpx.org/advanced/ssl/)
and [Python default SSL contexts](https://docs.python.org/3.12/library/ssl.html#ssl.create_default_context).
Model failure telemetry records only exception type and a stable TLS/HTTP category, never messages.

共享模型适配器显式使用系统信任库，保留证书和主机名校验；不从网络自动导入证书。
日志只记录安全错误分类与异常类型，不记录异常原文、密钥或对话正文。

For Agent planning HTTP failures, select one validated local plan and use local answer composition
for the rest of the turn. For answer HTTP failures, compose locally from already executed tool
outputs; do not search, rank or run tools again. Preserve the original deadline, concurrency,
tool and result caps. Cancellation, invalid model output, database failures and tool bugs remain
errors. Add nullable `fallback_reason: "llm_unavailable"` to JSON/SSE terminal results and report
`provider=local` when local composition supplies the answer. The UI labels automatic basic mode.

规划 HTTP 失败时使用一个经校验的本地计划；回答 HTTP 失败时复用已经执行的工具结果，保持排序。
自动降级有明确标识；取消、整体超时、非法模型输出及数据库错误仍按原错误路径处理。

The Agent recommendation tool accepts optional `intent=auto|theme|song` (default auto). Narrow
explicit mood/tempo phrases take priority over a model's song guess; quoted titles select song
mode. Theme mode invokes the same deterministic theme ranking even when catalog titles collide;
song mode retains ambiguity and never pads with unrelated fixtures. Return bounded ambiguity
choices to answer composition, so empty song results can ask for the artist. Persist the intent
as `seed_intent` on the existing assistant-message JSON; old conversations default to auto.
This requires no migration and does not change synchronous REST/MCP defaults or homepage rules.

助手工具增加可选意图；“emo的歌”“缓慢的歌”等明确主题不会因同名歌曲被清空，“推荐《emo》”仍按歌名确认。
意图随现有消息 JSON 保存，旧数据默认 auto，无数据库迁移。主题匹配基于已有元数据，不承诺 BPM 或情绪测量。

The browser holds an in-flight/failed message separately, appending a complete user/assistant pair
only after success. Retrying updates that pending message; deliberate repeats after success remain
new turns. This prevents visual duplication; it does not introduce server-side request idempotency
or reconcile a reply committed just before a network interruption.

## ADR-022: Ground homepage seed identification and keep display names separate from identity

**Status:** Accepted; supersedes ADR-020 only for seed identification and metadata display
**Date:** 2026-10-06

### Context / 背景

The source name `Faye Wong` obscures 王菲 in the homepage candidate list, while prose-only model
guidance cannot help an ambiguous or empty seed. A lone unlabelled recording is not proof of an
original artist. / 来源英文姓名与仅解释结果的模型调用无法解决起点歧义；单个未注明翻唱的版本不证明原唱。

### Decision / 决策

Keep reviewed original-artist hints for `我好想你` / 苏打绿 and `匆匆那年` / 王菲, with explicit
user selection taking precedence. For other homepage inputs, including one unverified version,
reuse the shared model adapter for strict `kind`/`title`/`artist` identification. Suggestions must
match real canonical catalog title/artist results; model output cannot create tracks, register
aliases, change scores or rank results. Unknown/invalid/unavailable identification retains artist
confirmation or unresolved state. A `model` source is labelled as catalog-matched assistance,
never original certification. Explicit themes retain fallback even during model outages; a model `theme` permits it
only when no recording title matched.

保留两首歌的已审核原唱提示，用户歌手选择优先。其他首页输入，即使只有一个未核实版本，也可通过共享模型
适配器返回严格 `kind`/`title`/`artist`，并与真实统一曲库标题/歌手匹配。模型不生成曲目、不登记别名、不改
评分与排序；未知、不合法或不可用时保留确认或未解析状态。模型结果注明已匹配曲库，不认证原唱。明确主题
在模型故障时仍保留降级，模型主题必须没有录音标题匹配才允许降级。

Use a small source-reviewed artist alias map for matching and optional presentation fields:
`Artist.display_name`, profile artist `display_name`, recent-feedback `artist_display_name`.
王菲 and 苏打绿 prefer Chinese labels in both locales; reviewed foreign names use English and
unknown names preserve source spelling. Merge alias recall metadata without replacing representative identity.
Preserve raw names, provider IDs, persisted affinity keys and canonical track keys; no migration.
Expose `seed_resolution_source` values `verified_hint`, `user`, `model`, `catalog`, `none` and keep
the source label visible across locale switches.

已核对来源的小型歌手别名表用于匹配和可选显示字段。王菲、苏打绿在两种界面语言下优先中文，已审核外国
歌手用英文，未知姓名保留来源写法；合并别名召回元数据，原始姓名、来源 ID、画像键与歌曲 key 不变，无迁移。
新增识别来源字段，切换语言保留标记。

Each homepage request shares at most three registry operations, one eight-second model call,
37 seconds of cumulative compute waiting and a 45-second total deadline; four active requests are
allowed. Identification
attempts use local guidance afterward (`guidance_provider=local`), avoiding a second model call.
Existing synchronous recommendation, Agent and MCP tools keep the deterministic core and do not
invoke this identification model. ADR-020's ranking, version filtering and legacy-runtime decisions
remain in force; ADR-021's shared DeepSeek transport behavior remains unchanged.

每个首页请求共用最多三次曲库查询、一次 8 秒模型调用、累计 37 秒计算等待和 45 秒总限时，并发上限四个。
尝试识别后使用本地说明，不追加第二次模型调用。同步推荐接口、Agent 与 MCP 工具继续使用确定性核心，
不调用识别模型；ADR-020 的排序、版本过滤与旧版保留决策及 ADR-021 的 DeepSeek 传输行为继续有效。

### Consequences / 影响

Reviewed evidence identifies the intended 王菲 artist without model availability; a matching
provider recording is still required. Other model
suggestions remain bounded and catalog-grounded, but catalog presence does not establish historical
authorship, and the alias table does not guarantee every artist's preferred name. Missing upstream
recordings can still require confirmation or yield fewer tracks. No dependency, credential or
database migration is added; offline tests do not establish live-model accuracy.

王菲案例可依靠已审核资料确定歌手，仍需匹配真实来源录音；其他模型建议仍受限并核对曲库，但不证明历史原唱，别名表也不保证
覆盖所有姓名。上游缺歌仍可能需要确认或返回较少曲目。没有新增依赖、凭据或数据库迁移；离线测试不证明
真实模型准确性。

## ADR-021: Keep DeepSeek compatibility at the shared model adapter boundary

**Status:** Accepted
**Date:** 2026-10-05

Explicitly send `thinking: {type: disabled}` only when the configured URL hostname is exactly
`api.deepseek.com`. Both the homepage and assistant reuse this adapter and existing `LLM_*`
environment variables. Preserve JSON output mode and strict schema validation for every provider;
custom endpoints and lookalike domain names retain their existing request payload.

DeepSeek enables thinking by default; its [Chat Completions documentation](https://api-docs.deepseek.com/api/create-chat-completion/)
supports disabling it and requesting JSON output. This keeps reasoning within existing request
deadlines without introducing a new credential, changing the configured model or removing
structured output from unrelated providers. Mocked transport checks do not certify live quality.

## ADR-020: Resolve recording seeds before discovery; optional shared model guidance

**Status:** Accepted; seed identification and metadata display superseded by ADR-022
**Date:** 2026-10-05

### Decision

Use a deterministic recording-resolution step before artist/attribute recall. Keep a small,
source-backed original-recording hint for the reported `我好想你` case; unknown multi-artist
matches require explicit artist selection. A single unlabelled match does not certify original
authorship. Filter alternate recordings before deduplication, exclude seed versions, and score
related artist/genre/tag/language factors explicitly alongside existing profile policy.
Bound each request to three registry operations and never pad a resolved song with unrelated
fixture tracks. Keep generic theme fallback and the existing recommendation response contract.

Add `/v1/recommendations/discover` for canonical seed metadata, ambiguity choices and explanation.
Reuse the assistant's configured LLM adapter for bounded prose only; errors preserve deterministic
results with local guidance. Translate homepage interface copy through an EN/中文 preference,
keeping music metadata and English theme headings unchanged.

### Consequences

Song discovery goes beyond a title search without handing recall/ranking to a model. Original
identification depends on source quality and bounded verified hints; incomplete upstream data
can produce fewer results or a request for clarification. Optional model prose can still be
inaccurate despite schema validation and grounding instructions; real-model quality is unverified.
No new dependency, database schema or legacy-runtime change is required.

## ADR-001: Incremental strangler migration from the legacy demo

**Status:** Accepted
**Date:** 2026-09-29

### Context

The repository contains a functioning static HTML/JavaScript demo with a Python standard
library proxy. The target platform requires a typed Next.js client, FastAPI service,
PostgreSQL/pgvector, Redis, tests, and Docker Compose.

### Decision

Build the target platform in new `apps/` and `services/` directories. Keep the legacy demo
unchanged until a replacement vertical slice is verified and documented.

### Consequences

- The demo remains runnable during the migration.
- New code avoids coupling to the large legacy front-end script.
- A temporary dual-runtime period is intentional and must be called out in the README.

## ADR-002: One Agent with allow-listed tools

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Use one orchestration Agent with a small tool registry: recommendation, read-only profile,
music knowledge retrieval and explanation (Phase 5 refinement in ADR-014). Traditional ranking owns candidate
quality and ordering.

### Consequences

- Tool selection can be tested deterministically.
- The system does not add multi-Agent coordination, queues, or hidden recommendation policy.
- Agent output must include tool provenance when it recommends songs.

## ADR-003: Anonymous device identity, not account authentication

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Issue a random client-side device identifier and accept it in a validated request header.
Persist preference profile and conversation linkage against that identifier.

### Consequences

- The project demonstrates personalization without the security and product scope of signup.
- There is no cross-device identity guarantee.
- The API will rate-limit and validate the identifier; it must never grant privileged access.

## ADR-004: PostgreSQL with pgvector; Redis only for ephemeral data

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Use PostgreSQL as the durable store and pgvector for song, preference, and knowledge vectors.
Use Redis only for sessions, cache, and rate-limit state.

### Consequences

- One durable database supports relational recommendation data and vector retrieval.
- Docker Compose must enable the pgvector extension via migration.
- Redis data can be discarded without losing users' durable preferences.

## ADR-005: Preserve and mine the legacy demo before migration

**Status:** Accepted

### Decision

Do not rewrite `app.js` or `server.py` in Phase 0. Treat the current user-visible behaviour as
an executable reference and migrate reusable logic only behind tests and canonical contracts.

### Consequences

- The legacy demo remains the only supported runtime during Phase 0.
- Existing provider mappings and rank heuristics become migration inputs, not target architecture.

## ADR-006: Limit target providers to verified adapters

**Status:** Accepted

### Decision

The target runtime will retain only two or three providers after an adapter verification spike.
Sources based on unstable public endpoints, scraped pages, or undocumented tokens remain optional
and never determine core availability.

### Consequences

- Provider capability and health are explicit.
- Multi-source recall remains a product feature without promising every legacy source indefinitely.

## ADR-007: Phase 1 persistence and startup

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Use synchronous SQLAlchemy 2.0 with psycopg and Alembic for the small Phase 1 data surface.
The API container runs migrations before serving requests. `GET /health` is a liveness check;
`GET /health/ready` verifies PostgreSQL and Redis. Anonymous device IDs are the primary key of
`device_users` and grant no permissions. SQLite is used only for fast local repository/API tests.

### Consequences

- A failed migration prevents API startup instead of serving against an outdated schema.
- Tests prove repository behaviour without Docker; live PostgreSQL migration still needs a
  Docker-capable environment.
- Redis is a connected ephemeral dependency, not a source of durable device identity.

## ADR-008: Fixture recommendation chain for Phase 1

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Expose `POST /v1/recommendations` with a bounded seed and limit. A service asks a small domain
function to select canonical songs from a committed JSON fixture; it moves tag matches first
and otherwise preserves fixture order. The Next.js shell fetches this response on request.

### Consequences

- The Web → API → domain path is executable without music providers or a catalog import.
- The fixture selector is not a production recall or ranking policy and is replaced in Phase 3.

## ADR-009: Canonical tracks and bounded provider registry

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Represent external songs as a canonical Track with Artist, optional Album, ProviderSource,
duration, artwork, URL, language, genres/tags, popularity and a normalized title/artist key.
Keep source payload parsing inside adapters. Expose a MusicProvider Protocol and registry that
returns per-source ProviderResult errors alongside canonical tracks. Calls are sequential
(upstream concurrency one), limited to 25 results/source, use four-second HTTP timeouts, have
no retries, and cap response bodies at 1 MB. Health is last-operation status, not an active
network probe. The key prepares for later deduplication but Phase 2 does not merge or rank songs.

iTunes Search API is the documented default source. NetEase is a default best-effort adapter
to preserve the second legacy source, with `unverified` capability metadata; QQ is opt-in via
`ENABLE_QQ_PROVIDER`. Both NetEase and QQ depend on undocumented public web endpoints and may
fail independently. Spotify and YouTube Music remain legacy-only and unverified for the target
runtime.

### Consequences

- API and future recommendation code consume one schema and never inspect provider payloads.
- A source outage appears in `sources` without discarding healthy source results.
- Automatic tests use fixtures and mocked HTTP; they cannot certify live upstream availability.

## ADR-010: Deterministic Phase 3 recommendation policy

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Recall from the bounded Provider Registry plus a versioned local catalog. Normalize title and
artist variants for cross-provider deduplication while retaining every source ID. Rank with
explicit weights in `app/domain/policy.py`, apply deterministic artist/provider/genre diversity
penalties, and construct explanations from measured factors. Return scores and source errors.

### Consequences

An upstream outage leaves catalog recommendations available. Future Agent tooling may invoke
this recommender but cannot replace its recall, rank, or explanation policy. Provider metadata
quality and the small fallback catalog limit relevance until a larger verified catalog exists.

## ADR-011: Latest feedback wins and profiles are durable snapshots

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Store one rating per anonymous device and canonical track key. Atomic PostgreSQL upsert replaces
earlier feedback; recompute a bounded recent profile in the same transaction. Store normalized
artist, genre, tag, and language affinities as JSON, and consult current disliked track keys
when ranking. The device header links preferences but grants no authentication privileges.

### Consequences

Feedback changes later recommendations without Redis or an LLM. A client may supply metadata
for its own anonymous profile; input sizes are bounded. The profile uses the latest 200 ratings
with explicit recency decay, so very old ratings are not represented in the snapshot.

## ADR-012: Small deterministic embeddings and versioned offline evaluation

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Use a 16-dimensional local SHA-256 feature hash for song and preference vectors. Persist vectors
in pgvector and expose a bounded repository cosine search; SQLite uses a local fallback for
offline tests. Embeddings do not silently modify ranking. Evaluate a committed five-song,
two-case fixture with relevance, personalization rank lift, attribute diversity, and coverage.

### Consequences

No paid API, model download, or training job is required. Hash collisions and tiny fixture size
limit retrieval and metric generalization; evaluation measures regression on fixed cases, not
real-user recommendation quality. Live pgvector migration/query verification awaits a PostgreSQL
runtime on a Docker-capable host.

## ADR-013: Browser API client and read-only profile projection

**Status:** Accepted
**Date:** 2026-09-29

### Decision

The Phase 4 Next.js page runs its interactive requests in the browser against the versioned
FastAPI endpoints. One API module owns the public base URL, device header, timeout, JSON parsing,
and error envelope. The browser persists only a random anonymous device ID. A new read-only
`GET /v1/profile` projects positive affinities and five recent ratings from Phase 3 tables; it
does not change the recommendation policy or persistence model.

### Consequences

The browser can show durable feedback and partial provider failures without an additional BFF.
Deployments must set `NEXT_PUBLIC_API_BASE_URL` to a browser-reachable API URL and allow the web
origin in `ALLOWED_ORIGINS`. The profile is tied to one browser identifier with no account
recovery or cross-device sync.

## ADR-014: One validated plan with replaceable LLM adapters

**Status:** Accepted
**Date:** 2026-09-30

### Decision

Separate Agent core/tools/memory/prompts/schemas/provider adapters. A local deterministic intent
router is the default and fallback when no Key exists. An optional OpenAI-compatible JSON adapter
implements the same `LLMProvider` contract. Validate a single plan before executing 1–4 distinct,
allowlisted calls, then validate a prose-only answer. No retries, autonomous replanning, feedback
writes, ranking mutation or multiple Agents. Canonical recommended items come exclusively from
the Phase 3 pipeline. SSE exposes public statuses, tool names and final output, never reasoning.

### Consequences

Mock transport and local routing make tests independent of keys/network. The local provider has
limited bilingual patterns; real model answers can still be inaccurate despite grounding prompts.
Schema checks protect structure, not factual truth. Four active requests and four worker slots per
event loop plus bounded I/O prevent unlimited concurrency; timeouts cannot terminate an already
running synchronous operation. Live model compatibility is unverified.

## ADR-015: PostgreSQL conversation context and derived preference summaries

**Status:** Accepted
**Date:** 2026-09-30

### Decision

Persist the last six turns and last seed per server-issued conversation UUID in PostgreSQL.
Bind each conversation to its validated anonymous device ID. Reject stale simultaneous writes
with a version check. Store a top-five affinity summary derived by the profile tool from existing
feedback. Use no accounts and no LLM-authored durable preference facts. Redis remains optional
for future ephemeral caching rather than required for Agent memory.

### Consequences

Context survives restarts and can be resumed by conversation ID. Device IDs remain identifiers
with no authentication guarantee. The frontend retains the conversation ID within its current
page only; history listing, deletion, TTL cleanup and cross-device sync are outside Phase 5.
Chat text is stored in bounded context rows but excluded from structured logs.

## ADR-016: Small lexical-guarded RAG and independent MCP-style search

**Status:** Accepted
**Date:** 2026-09-30

### Decision

Seed four versioned knowledge documents/chunks with local 16-dimensional text hash vectors.
Use PostgreSQL pgvector cosine candidates followed by lexical-overlap guarding and bounded
retrieval ranking. Knowledge aids Q&A and explanations only. Expose independent `music_search`
through an HTTP MCP-style schema/call façade using canonical input/output models and no LLM.

### Consequences

All fixtures and retrieval tests run offline. Hash collisions and sparse aliases limit semantics;
no relevant lexical evidence produces no answer material. The minimal MCP tools contract is not
a complete MCP transport or JSON-RPC server. No new dependency or large dataset is introduced.
SQLite verifies persistence/retrieval semantics, and offline Alembic SQL verifies PostgreSQL
DDL/fixture seeding; live pgvector execution remains unverified on this host.

## ADR-017: Correlated content-free JSON telemetry

**Status:** Accepted
**Date:** 2026-09-30

### Decision

Use a small ContextVar-based ASGI boundary and JSON event allowlist rather than a monitoring stack.
Carry request/trace IDs through HTTP, SSE, worker threads and outbound adapter headers. Log duration,
status, counts, model/provider and optional validated usage. Preserve the recommendation response's
request_id field but align it with the response header. Disable raw HTTP client/access logging in
the documented runtime. Never record request/chat/provider/LLM payloads or exception messages.

### Consequences

No collector or dashboard is required. Logs provide samples for later aggregation, not a complete
OTel trace or built-in histogram/alert service. SSE errors require event-level inspection after HTTP
200. A central body limit and generic unexpected-error envelope prevent unbounded JSON input and
sensitive exception disclosure. Anonymous device linkage still is not authentication.

## ADR-018: Add standard MCP stdio alongside the existing HTTP façade

**Status:** Accepted; supersedes ADR-016 only for the transport scope
**Date:** 2026-09-30

### Decision

Install official Python MCP SDK 1.30.0 as an optional exact-pinned extra. Use its supported v1
stdio API to expose read-only music_search and recommend_tracks, reusing MusicTools and the
recommendation service. Verify initialize/list/call with an actual SDK client subprocess. Preserve
Phase 5 HTTP routes and name them MCP-style façade. No remote MCP auth/HTTP endpoint in this phase.

### Consequences

Compatible local clients can actually invoke music tools without another service or an LLM. Stdio
stdout is reserved for protocol messages and logs use stderr. Recommendations are unpersonalized;
no private device data is exposed. SDK v1 remains maintained for security/critical fixes; a future
v2 migration must be deliberate. RAG and deterministic ranking decisions in ADR-016 remain intact.

## ADR-019: Offline release gates and explicit clean-start evidence

**Status:** Accepted
**Date:** 2026-09-30

### Decision

GitHub Actions runs API and web quality gates plus a disposable Compose project. Generate a unique
CI-only database credential at runtime; disable music providers and use the local Agent. Verify
migrations, pgvector query, Redis, readiness, web, recommendation, feedback/profile and local Agent
with the existing business layer. Ship typed package discovery, wheel fixtures and non-root
containers. Keep author-host verification distinct from CI-host verification.

### Consequences

Quality gates need dependency/image downloads but no real music/LLM API or Key. Author Windows has
no Docker, so local clean start is explicitly unexecuted; never infer success from static YAML/SQL.
The next Docker-capable run provides live evidence. Transitive Python packages and container tags
remain unlocked, which limits bit-for-bit reproducibility. No public deployment or main merge is
performed as part of the final engineering phase.
