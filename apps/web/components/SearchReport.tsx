import type { InterfaceLanguage, SearchReport as Report } from "../types/music";
import { copyFor } from "../lib/i18n";

export function platformName(name: string) {
  return ({ itunes: "Apple Music", netease: "网易云 / NetEase", qq: "QQ Music", musicbrainz: "MusicBrainz",
    kugou: "酷狗 / Kugou", kuwo: "酷我 / Kuwo", brave: "Brave Search" } as Record<string, string>)[name] ?? name;
}

export default function SearchReport({ report, language }: { report?: Report | null; language: InterfaceLanguage }) {
  if (!report) return null;
  const copy = copyFor(language);
  const labels = language === "zh" ? {
    hit: "返回录音", no_results: "无结果", error: "来源故障", not_configured: "未配置",
    not_executed: "未执行", unavailable: "暂不可用", auth_required: "需要授权",
  } : { hit: "Recordings returned", no_results: "No results", error: "Source failure", not_configured: "Not configured",
    not_executed: "Not searched", unavailable: "Unavailable", auth_required: "Authorization required" };
  const reasons: Record<string, string> = language === "zh" ? { matched: "已匹配", ambiguous: "等待版本选择",
    not_found: "未找到匹配", budget_exhausted: "请求预算用尽", deadline: "达到总时限", partial_failure: "部分来源故障",
    unavailable: "来源不可用", unsupported_platform: "平台未接入" } : { matched: "Matched", ambiguous: "Choose a version",
    not_found: "No match", budget_exhausted: "Request budget reached", deadline: "Time limit reached",
    partial_failure: "Some sources failed", unavailable: "Source unavailable", unsupported_platform: "Unsupported platform" };
  return <details className="search-report">
    <summary>{copy.searchReport} · {reasons[report.end_reason] ?? report.end_reason}</summary>
    {report.incomplete ? <p className="notice">{copy.searchIncomplete}</p> : null}
    <ul>{report.attempts.map((attempt, i) => <li key={i}>
      {platformName(attempt.platform)}{attempt.region ? ` (${attempt.region})` : ""} · {labels[attempt.status]}
      {attempt.result_count ? ` (${attempt.result_count})` : ""}
      {attempt.error_code === "timeout" ? language === "zh" ? " · 超时" : " · Timeout" : null}
    </li>)}</ul>
    <p>{language === "zh" ? `外部请求：${report.external_requests}` : `External requests: ${report.external_requests}`}</p>
  </details>;
}
