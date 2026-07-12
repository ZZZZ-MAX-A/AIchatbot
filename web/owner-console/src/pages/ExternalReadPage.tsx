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
            <article className="metric-tile"><span>搜索模式</span><strong>{data.search_depth}</strong></article>
            <article className="metric-tile"><span>最多结果</span><strong>{data.max_results}</strong></article>
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
                  <div><dt>外部请求数</dt><dd>{safeCount(data.recent_task.external_request_count)}</dd></div>
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
              <StatusBadge label="主人私聊严格命令" value={yesNo(data.boundary.owner_private_strict_command_only)} tone="success" />
              <StatusBadge label="Main LLM 触发" value={data.boundary.main_llm_can_trigger ? "允许" : "禁止"} tone={data.boundary.main_llm_can_trigger ? "danger" : "success"} />
              <StatusBadge label="普通聊天触发" value={data.boundary.ordinary_chat_can_trigger ? "允许" : "禁止"} tone={data.boundary.ordinary_chat_can_trigger ? "danger" : "success"} />
              <StatusBadge label="任意 URL" value={data.boundary.arbitrary_url_fetch_allowed ? "允许" : "禁止"} tone={data.boundary.arbitrary_url_fetch_allowed ? "danger" : "success"} />
              <StatusBadge label="AI answer / raw / images" value="关闭" tone="success" />
              <StatusBadge label="retry / fallback" value="关闭" tone="success" />
              <StatusBadge label="实时探测" value={data.boundary.live_probe_executed ? "已执行" : "未执行"} tone={data.boundary.live_probe_executed ? "danger" : "success"} />
              <StatusBadge label="Query / 正文 / URL 暴露" value="否" tone="success" />
              <StatusBadge label="凭据值暴露" value={data.boundary.credential_value_exposed ? "是" : "否"} tone={data.boundary.credential_value_exposed ? "danger" : "success"} />
            </div>
            <p className="panel-note">本页不执行实时网络探测。这里的正常只表示本地配置、依赖兼容性和最近任务元数据符合预期，不能证明 Tavily 此刻可达。</p>
          </section>
        </>
      ) : null}
    </section>
  );
}
