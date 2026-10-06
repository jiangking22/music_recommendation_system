# Recording resolution / 自动扩展音乐检索

The homepage, **None of the above**, and manual source recovery share a recording resolver.
It revalidates confirmed success records first, then searches Apple, NetEase and QQ, followed
by Apple Taiwan/Hong Kong and MusicBrainz. Queries use bounded artist-qualified forms,
reviewed aliases and normalized punctuation. Identical platform/region/query combinations
are not repeated. Expansion stops when a matching title/artist recording is found; covers,
live versions and unrelated titles do not qualify. Catalog presence does not certify authorship.

首页、**以上均没有** 和人工补查共用录音解析服务。依次重新核实成功记录、检索 Apple／网易云／QQ，
再扩展 Apple 台湾／香港与 MusicBrainz；使用歌名、歌名＋歌手、已审核别名与规范化标点，避免重复查询。
核实命中后停止扩展；同名不同歌手、明确翻唱或现场版本不会冒充匹配。曲库存在性不等于原唱认证。

MusicBrainz provides recording metadata, not playback; requests share a one-per-second limiter
and an identifying User-Agent ([API documentation](https://musicbrainz.org/doc/MusicBrainz_API)).
Kugou and Kuwo are explicitly **unavailable**, rather than reported as searched: on 2026-10-06
the former failed to connect and the latter rejected the public request. They have no enabled
adapter. Each report distinguishes returned recordings, empty results, errors, authorization,
unconfigured sources and sources not executed. An incomplete budget or source failure never
means that the song does not exist.

MusicBrainz 仅核对录音元数据，界面明确说明不提供播放。酷狗连接失败、酷我公开请求被拒绝，当前均标为
**暂不可用**，未启用适配器。报告分别列出返回录音、无结果、故障、需要授权、未配置和未执行；预算用尽
或网络故障显示“检索尚未完成”。最终未命中提示：**未在已检索平台找到该歌曲，请检查歌名、歌手或来源链接。**

Optional `BRAVE_SEARCH_API_KEY` enables a maximum of five web clues per search. It is disabled
without its own server-side key ([Brave authentication](https://api-dashboard.search.brave.com/documentation/guides/authentication)).
Snippets are never recordings: registered provider detail lookup must return matching canonical
metadata. The server parses only supported HTTPS song links; it never fetches the supplied URL,
follows a redirect, runs webpage code or trusts model-generated recording IDs.

可选 `BRAVE_SEARCH_API_KEY` 为独立服务端 Key，不配置时默认关闭网页搜索。摘要仅为线索；必须读取已接入
平台的真实详情数据才能形成录音。用户链接仅解析受支持域名与录音 ID，服务端调用固定平台接口，不直接
抓取输入 URL、跟随重定向或执行网页代码。现支持 Apple US/TW/HK、网易云歌曲链接、QQ songDetail 链接
和 MusicBrainz recording 链接；其他平台／链接格式明确提示暂不支持。

Automatic discovery has a 45-second total deadline, at most one model call (8 seconds), and
24 external requests (one reserved for the optional model; reports count catalog/web calls).
Music work has a 37-second deadline; expansion reserves four requests
for deterministic related recall. Providers run sequentially within one request (below the
maximum of two); all HTTP catalog/web calls share four global outbound slots. Discovery,
identification and manual recovery share four active request slots and the existing bounded
worker pool. Each adapter retains four-second timeouts, a 1 MB response cap and 25 recordings.
Manual recovery has 30 seconds and six external requests, without automatic retry loops.

自动流程总限时 45 秒、模型最多一次且限时 8 秒、外部请求最多 24 次，其中为模型预留一次，报告计数为曲库／
网页请求。曲库工作限时 37 秒，扩展预留四次
请求用于确定性召回。每请求顺序调用来源，满足最多两个来源并发的上限；全局外部 HTTP 并发最多四个。
三个入口共享四个请求槽与有界工作池。适配器保留 4 秒超时、1 MB 响应与每来源 25 首上限；人工补查
限时 30 秒、最多六次外部请求，不自动循环重试。日志仅记录关联 ID、来源、阶段、状态、计数、耗时和错误码。

`POST /v1/recordings/resolve` accepts `seed` (1–120 trimmed characters), optional `artist`
(1–200), `language=en|zh`, optional `platform` (1–40) and `song_url` (1–2048).
It returns `status=matched|ambiguous|not_found|unsupported_platform|unavailable|incomplete`,
nullable `matched_track`/`resolution_id`, bounded candidate tracks with their references,
`search_report` and canonical `sources`. It performs no recommendation or model call.
Discovery and identify-original add `search_report` and nullable `resolution_id`; discovery
also returns `candidate_resolutions`. Identification retains its existing model error codes.
When initial discovery matches a model-derived artist it adds `requires_confirmation=true`,
returns a real `seed_track`/reference and empty `items`, and does not recall or rank until explicit
artist confirmation. Other discovery branches default this flag to false.

新增解析接口不调用模型、不生成推荐。发现／补充识别响应增加 `search_report` 与 `resolution_id`，
多版本候选分别附带确认引用。报告包含平台、地区、阶段、操作、状态、数量、安全错误码、请求计数和结束原因。
旧参数 `seed_artist`、`seed_storefront=TW|HK` 继续兼容。
首次匹配模型歌手时新增 `requires_confirmation=true`，返回核实录音与引用但不生成推荐，等待用户确认。

The UI retains the original query and model suggestion. Unresolved results offer a platform
selector, optional artist and song-link field; multiple recordings require a choice, and a single
recording still requires **Confirm and recommend**. Confirmation sends `resolution_id` plus
`seed_artist` to discovery. The server re-fetches the same provider ID before deterministic recall
and ranking. Expired, mismatched or unavailable references return `resolution_expired` (410),
`resolution_mismatch` (422) or `resolution_unavailable` (503). New searches cancel pending UI
lookups; late results cannot replace the next query. English and Chinese copy cover the flow.
Both initial and rejected-candidate model suggestions offer **Different artist — I'll provide it**.
That action hides the model's confirmation button and requires a supplied artist. The manual
resolver defaults to automatic platform expansion, with optional source restrictions. Selecting
the verified recording uses its own reference and is not labeled as confirming the rejected model
artist. Editing artist/platform/link removes stale recording choices but retains report history.

未命中时保留原查询／模型建议／历史报告，并提供指定来源补查。单个或多个真实录音均先展示来源并等待确认，
确认携带引用后从原命中平台重新核实，再由原推荐器召回和排序。重复提交被禁用，新查询取消旧请求，迟到
响应不会覆盖新结果；失效确认可重新检索，不强行推荐。
首次与补充模型建议都可选择“不是这位歌手，我来填写”；填写歌手、核实录音并确认后再推荐。
默认自动检索平台，修改输入清除旧确认按钮；被否定的模型歌手不会作为成功记录保存。

Migration `0006_recording_resolution` adds `recording_resolutions` (30-minute verification
references, expired rows pruned when new references are issued) and `verified_recordings`
(canonical title, artist identity, platform, real recording ID, URL, region and verification time).
Only a fresh provider verification plus explicit reference confirmation upserts success memory.
Guesses, failed lookups and unconfirmed tracks are never saved as durable facts. Future searches
revalidate remembered IDs; missing IDs are marked stale and other platforms are searched. Homonyms
remain separate. This is successful-result memory, not model training or global original-author certification.

迁移新增临时核实引用和成功录音表；仅“平台核实成功＋用户明确确认采用”写入成功记录。下次优先重查该
平台与 ID，失效记录标为待核实并继续扩展；同名不同歌手分别存储。此机制不训练模型、不建立原唱认证，
不修改评分规则。现有 Compose API 启动流程执行 Alembic 迁移；升级应保留现有 `.env` 和数据库卷。

The legacy `python server.py` demo remains unchanged. Synchronous recommendation REST/Agent/MCP
retain their existing bounded registry contract and deterministic theme behavior; expanded resolution
belongs to the homepage and recording endpoints. Automated tests mock providers/models; live source,
model and browser checks are recorded separately and do not establish universal coverage or accuracy.

旧版演示保持可运行；原同步推荐、Agent 和 MCP 的现有契约／主题处理保持兼容。自动测试模拟平台和模型，
真实平台、已配置模型与浏览器验收单独记录；不能保证所有歌曲均被收录或始终可访问。
