import { useOutletContext } from "react-router-dom";

import type { OwnerConsoleSnapshot } from "../api/ownerConsoleTypes";
import { EmptyState } from "../components/EmptyState";

type PlaceholderPageProps = {
  title: string;
};

const routeNameLabels: Record<string, string> = {
  routes: "路由契约",
  overview: "概览",
  tasks: "任务",
  "tasks.detail": "任务详情",
  approvals: "审批",
  "approvals.detail": "审批详情",
  diagnostics: "诊断",
  memory: "记忆",
  "access-control": "访问控制",
  settings: "设置",
};

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  const snapshot = useOutletContext<OwnerConsoleSnapshot>();
  const routeRows = snapshot.routes?.data?.rows ?? [];

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="page-header__eyebrow">主人控制台</p>
          <h1>{title}</h1>
        </div>
        <span className="page-header__resource">只读页面</span>
      </header>

      <section className="read-only-panel">
        <h2>只读接口状态</h2>
        <dl className="summary-grid">
          <div>
            <dt>接口前缀</dt>
            <dd>{snapshot.routes?.data?.api_prefix ?? "等待加载"}</dd>
          </div>
          <div>
            <dt>开放方法</dt>
            <dd>{snapshot.routes?.data?.allowed_methods?.join(", ") ?? "GET"}</dd>
          </div>
          <div>
            <dt>资源路由</dt>
            <dd>{snapshot.routes?.data?.route_count ?? 0} 个</dd>
          </div>
          <div>
            <dt>写入入口</dt>
            <dd>
              {snapshot.routes?.data?.write_routes_enabled === false
                ? "已关闭"
                : "等待确认"}
            </dd>
          </div>
        </dl>
      </section>

      {title === "概览" ? (
        <section className="route-table-panel">
          <h2>只读资源</h2>
          <div className="route-table" role="table" aria-label="只读资源路由">
            <div className="route-table__row route-table__row--head" role="row">
              <span role="columnheader">资源</span>
              <span role="columnheader">方法</span>
              <span role="columnheader">路径</span>
              <span role="columnheader">网页写入</span>
            </div>
            {routeRows.map((row) => (
              <div className="route-table__row" role="row" key={row.name}>
                <span role="cell">{routeNameLabels[row.name] ?? row.name}</span>
                <span role="cell">{row.method}</span>
                <span role="cell">{row.path}</span>
                <span role="cell">
                  {row.web_write_enabled ? "已开启" : "已关闭"}
                </span>
              </div>
            ))}
          </div>
        </section>
      ) : (
        <EmptyState
          title="暂无业务快照"
          description="当前资源没有可显示的只读数据。"
        />
      )}
    </section>
  );
}
