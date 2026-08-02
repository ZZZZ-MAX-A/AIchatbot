import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ownerConsoleApi } from "../api/ownerConsoleApi";
import type { OwnerConsoleExternalReadEnvelope } from "../api/ownerConsoleTypes";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";

function yesNo(value: boolean): string {
  return value ? "是" : "否";
}

function safeCount(value: number | null): string {
  return value === null ? "未知" : String(value);
}

export function ExternalReadPage() {
  const [loading, setLoading] = useState(true);
  const [envelope, setEnvelope] = useState<OwnerConsoleExternalReadEnvelope | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      setEnvelope(await ownerConsoleApi.getExternalRead(signal));
    } catch (exc) {
      if (exc instanceof DOMException && exc.name === "AbortError") return;
      setError(exc instanceof Error ? exc.message : "联网状态加载失败");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const data = envelope?.data;
  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="page-header__eyebrow">MainAgent · 本地只读观测</p>
          <h1>外部只读查询</h1>
        </div>
        <button className="refresh-button" type="button" onClick={() => void load()} disabled={loading}>
          <RefreshCw aria-hidden="true" size={16} />
          <span>刷新状态</span>
        </button>
      </header>

      {loading ? <section className="loading-panel" role="status">正在读取本地联网状态</section> : null}
      {error ? <ErrorState title="联网状态暂不可用" description={error} /> : null}

      {data ? (
        <>
          <section className="metric-grid" aria-label="联网配置概览">
            <article className="metric-tile"><span>功能开关</span><strong>{data.enabled ? "已开启" : "已关闭"}</strong></article>
            <article className="metric-tile"><span>执行器</span><strong>{data.executor_configured ? "已就绪" : "未就绪"}</strong></article>
            <article className="metric-tile"><span>隔离综合</span><strong>{data.synthesis_configured ? "已配置" : "安全回退"}</strong></article>
            <article className="metric-tile"><span>搜索模式</span><strong>{data.search_depth}</strong></article>
            <article className="metric-tile"><span>每阶段最多结果</span><strong>{data.max_results}</strong></article>
          </section>

          <section className="detail-grid">
            <article className="detail-panel">
              <h2>固定 Provider</h2>
              <dl className="detail-list">
                <div><dt>Provider</dt><dd>{data.provider_name}</dd></div>
                <div><dt>Endpoint host</dt><dd>{data.endpoint_host}</dd></div>
                <div><dt>凭据已配置</dt><dd>{yesNo(data.credential_configured)}</dd></div>
                <div><dt>超时</dt><dd>{data.timeout_seconds} 秒</dd></div>
                <div><dt>httpx</dt><dd>{data.dependencies.httpx_version}</dd></div>
                <div><dt>httpcore</dt><dd>{data.dependencies.httpcore_version}</dd></div>
              </dl>
              <div className="detail-panel__footer">
                <StatusBadge label="依赖兼容" value={data.dependencies.compatible ? "是" : "否"} tone={data.dependencies.compatible ? "success" : "danger"} />
              </div>
            </article>

            <article className="detail-panel">
              <h2>最近正式任务</h2>
              {data.recent_task.available ? (
                <dl className="detail-list">
                  <div><dt>任务</dt><dd>#{data.recent_task.task_id}</dd></div>
                  <div><dt>任务状态</dt><dd>{data.recent_task.task_status || "未知"}</dd></div>
                  <div><dt>Provider</dt><dd>{data.recent_task.provider_name || "未知"}</dd></div>
                  <div><dt>结果数</dt><dd>{safeCount(data.recent_task.result_count)}</dd></div>
                  <div><dt>来源主机数</dt><dd>{safeCount(data.recent_task.source_host_count)}</dd></div>
                  <div><dt>丢弃结果数</dt><dd>{safeCount(data.recent_task.dropped_result_count)}</dd></div>
                  <div><dt>Provider 候选数</dt><dd>{safeCount(data.recent_task.provider_candidate_count)}</dd></div>
                  <div><dt>官方正文强日期数</dt><dd>{safeCount(data.recent_task.official_content_strong_count)}</dd></div>
                  <div><dt>失败检索阶段</dt><dd>{data.recent_task.failed_search_stage || "无"}</dd></div>
                  <div><dt>检索阶段数</dt><dd>{safeCount(data.recent_task.search_stage_count)}</dd></div>
                  <div><dt>规划模式</dt><dd>{data.recent_task.planning_mode || "未知"}</dd></div>
                  <div><dt>业务场景</dt><dd>{data.recent_task.scene || "未知"}</dd></div>
                  <div><dt>第一阶段来源</dt><dd>{data.recent_task.primary_source_scope || "未知"}</dd></div>
                  <div><dt>第二阶段来源</dt><dd>{data.recent_task.secondary_source_scope || "none"}</dd></div>
                  <div><dt>第二阶段条件</dt><dd>{data.recent_task.secondary_mode || "none"}</dd></div>
                  <div><dt>第一阶段候选数</dt><dd>{safeCount(data.recent_task.official_stage_candidate_count)}</dd></div>
                  <div><dt>第一阶段合格数</dt><dd>{safeCount(data.recent_task.official_stage_result_count)}</dd></div>
                  <div><dt>第二阶段候选数</dt><dd>{safeCount(data.recent_task.media_stage_candidate_count)}</dd></div>
                  <div><dt>第二阶段合格数</dt><dd>{safeCount(data.recent_task.media_stage_result_count)}</dd></div>
                  <div><dt>日期缺失丢弃</dt><dd>{safeCount(data.recent_task.dropped_missing_date_count)}</dd></div>
                  <div><dt>窗口外丢弃</dt><dd>{safeCount(data.recent_task.dropped_outside_window_count)}</dd></div>
                  <div><dt>仅弱日期丢弃</dt><dd>{safeCount(data.recent_task.dropped_weak_only_count)}</dd></div>
                  <div><dt>日期冲突丢弃</dt><dd>{safeCount(data.recent_task.dropped_conflicting_date_count)}</dd></div>
                  <div><dt>注入嫌疑丢弃</dt><dd>{safeCount(data.recent_task.dropped_injection_count)}</dd></div>
                  <div><dt>清洗/去重/预算丢弃</dt><dd>{safeCount(data.recent_task.dropped_sanitization_count)}</dd></div>
                  <div><dt>来源策略丢弃</dt><dd>{safeCount(data.recent_task.dropped_source_policy_count)}</dd></div>
                  <div><dt>外部请求数</dt><dd>{safeCount(data.recent_task.external_request_count)}</dd></div>
                  <div><dt>Provider 请求</dt><dd>{safeCount(data.recent_task.provider_request_count)}</dd></div>
                  <div><dt>综合请求</dt><dd>{safeCount(data.recent_task.synthesis_request_count)}</dd></div>
                  <div><dt>综合状态</dt><dd>{data.recent_task.synthesis_status || "未知"}</dd></div>
                  <div><dt>综合错误类别</dt><dd>{data.recent_task.synthesis_error_category || "无"}</dd></div>
                  <div><dt>主人质量</dt><dd>{data.recent_task.owner_quality_status || "未知"}</dd></div>
                  <div><dt>状态类别</dt><dd>{data.recent_task.status_category || "未知"}</dd></div>
                  <div><dt>错误类别</dt><dd>{data.recent_task.error_category || "无"}</dd></div>
                  <div><dt>更新时间</dt><dd>{data.recent_task.updated_at || "未知"}</dd></div>
                </dl>
              ) : (
                <EmptyState title="暂无安全任务快照" description="尚未找到属于当前主人私聊上下文的正式 external-read 任务元数据。" />
              )}
            </article>
          </section>

          <section className="detail-panel">
            <h2>安全边界</h2>
            <div className="boundary-grid">
              <StatusBadge label="显式 /agent 为唯一入口" value={yesNo(data.boundary.owner_private_strict_command_only)} tone={data.boundary.owner_private_strict_command_only ? "success" : "danger"} />
              <StatusBadge label="/agent 内 MainAgent 选择联网" value={data.boundary.main_llm_can_trigger ? "允许" : "禁止"} tone={data.boundary.main_llm_can_trigger ? "success" : "warning"} />
              <StatusBadge label="日常聊天注入 MainAgent" value={data.boundary.ordinary_chat_can_trigger ? "异常" : "禁止"} tone={data.boundary.ordinary_chat_can_trigger ? "danger" : "success"} />
              <StatusBadge label="任意 URL" value={data.boundary.arbitrary_url_fetch_allowed ? "允许" : "禁止"} tone={data.boundary.arbitrary_url_fetch_allowed ? "danger" : "success"} />
              <StatusBadge label="Tavily AI answer / images" value="关闭" tone="success" />
              <StatusBadge label="Tavily raw content" value={data.boundary.raw_content_enabled ? "启用" : "关闭"} tone={data.boundary.raw_content_enabled ? "danger" : "success"} />
              <StatusBadge label="零工具隔离综合" value={data.boundary.isolated_synthesis_enabled ? "启用" : "关闭"} tone="success" />
              <StatusBadge label="retry / provider fallback" value="关闭" tone="success" />
              <StatusBadge label="实时探测" value={data.boundary.live_probe_executed ? "已执行" : "未执行"} tone={data.boundary.live_probe_executed ? "danger" : "success"} />
              <StatusBadge label="本状态页暴露 Query / 正文 / URL" value="否" tone="success" />
              <StatusBadge label="凭据值暴露" value={data.boundary.credential_value_exposed ? "是" : "否"} tone={data.boundary.credential_value_exposed ? "danger" : "success"} />
            </div>
            <p className="panel-note">本页不执行实时网络探测。MainAgent 先选择业务场景、来源范围、时间和证据角色；运行时仍强制最多两次固定 Tavily 读取、最多一次隔离综合、零自动重试与零 Provider 回退。官方正文强日期仅限固定官方域名、明确发布语义和唯一窗口内完整日期通过本地规则；这里的正常只表示本地配置、依赖兼容性和最近任务元数据符合预期，不能证明 Tavily 此刻可达。</p>
          </section>
        </>
      ) : null}
    </section>
  );
}
