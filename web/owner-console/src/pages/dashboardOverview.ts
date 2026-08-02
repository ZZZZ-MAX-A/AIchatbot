import type {
  OwnerConsoleExternalReadSnapshot,
  OwnerConsoleHealthSnapshot,
  OwnerConsoleOverview,
  OwnerConsoleReliabilitySnapshot,
  OwnerConsoleReliabilityTrendItem,
} from "../api/ownerConsoleTypes";
import type { OwnerConsoleWebWriteState } from "../app/ownerConsoleAccessStatus";

export type DashboardTone = "neutral" | "success" | "warning" | "danger";
export type DashboardSourceKey =
  | "overview"
  | "diagnostics"
  | "external_read"
  | "reliability";

export type DashboardAttentionItem = {
  id: string;
  tone: Exclude<DashboardTone, "success">;
  title: string;
  detail: string;
  route: string;
  actionLabel: string;
};

export type DashboardSourceSnapshot = {
  key: DashboardSourceKey;
  label: string;
  available: boolean;
  generatedAt: string;
  stale: boolean;
};

export type DashboardOverviewViewModel = {
  overall: {
    tone: DashboardTone;
    label: string;
    headline: string;
    detail: string;
  };
  attentionItems: DashboardAttentionItem[];
  actionableCount: number;
  reliability: {
    failureOccurrences: number;
    failureGroups: number;
    activeGroups: number;
    recoveredGroups: number;
    insufficientGroups: number;
    topItem: OwnerConsoleReliabilityTrendItem | null;
  };
  security: {
    checkedCount: number;
    expectedCount: number;
    violationLabels: string[];
  };
  sources: DashboardSourceSnapshot[];
  availableSourceCount: number;
  staleSourceCount: number;
};

type DashboardOverviewInput = {
  overview: OwnerConsoleOverview | null;
  webWriteState: OwnerConsoleWebWriteState;
  diagnostics: OwnerConsoleHealthSnapshot | null;
  externalRead: OwnerConsoleExternalReadSnapshot | null;
  reliability: OwnerConsoleReliabilitySnapshot | null;
  unavailableSources: DashboardSourceKey[];
  nowMs?: number;
  staleAfterMs?: number;
};

const SOURCE_LABELS: Record<DashboardSourceKey, string> = {
  overview: "任务与审批",
  diagnostics: "诊断快照",
  external_read: "联网配置",
  reliability: "结构化可靠性",
};

const ATTENTION_PRIORITY: Record<DashboardAttentionItem["tone"], number> = {
  danger: 0,
  warning: 1,
  neutral: 2,
};

const RELIABILITY_PRIORITY: Record<string, number> = {
  recurring: 0,
  unresolved: 1,
  insufficient_evidence: 2,
  recovered: 3,
};

const DIAGNOSTIC_SECTIONS = [
  "bot_status",
  "diagnostics",
  "config",
  "vision",
  "image_cache",
  "memory",
  "tts",
  "recent_errors",
] as const;

const DIAGNOSTIC_SECTION_LABELS: Record<(typeof DIAGNOSTIC_SECTIONS)[number], string> = {
  bot_status: "Bot 状态",
  diagnostics: "运行诊断",
  config: "配置",
  vision: "图片识别",
  image_cache: "图片缓存",
  memory: "记忆",
  tts: "语音",
  recent_errors: "最近错误",
};

function sourceGeneratedAt(
  key: DashboardSourceKey,
  input: DashboardOverviewInput,
): string {
  if (key === "overview") return input.overview?.generated_at ?? "";
  if (key === "diagnostics") return input.diagnostics?.generated_at ?? "";
  if (key === "external_read") return input.externalRead?.generated_at ?? "";
  return input.reliability?.generated_at ?? "";
}

function isStaleTimestamp(value: string, nowMs: number, staleAfterMs: number): boolean {
  if (!value) return false;
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) || nowMs - timestamp > staleAfterMs;
}

function topReliabilityItem(
  rows: OwnerConsoleReliabilityTrendItem[],
): OwnerConsoleReliabilityTrendItem | null {
  return (
    [...rows].sort((left, right) => {
      const statePriority =
        (RELIABILITY_PRIORITY[left.recovery_state] ?? 9) -
        (RELIABILITY_PRIORITY[right.recovery_state] ?? 9);
      if (statePriority !== 0) return statePriority;
      if (left.occurrence_count !== right.occurrence_count) {
        return right.occurrence_count - left.occurrence_count;
      }
      return Date.parse(right.last_seen_at) - Date.parse(left.last_seen_at);
    })[0] ?? null
  );
}

function buildSecurityPosture(input: DashboardOverviewInput) {
  const boundary = input.overview?.boundary;
  if (!boundary) {
    return {
      checkedCount: 0,
      expectedCount: 8,
      violationLabels: [] as string[],
    };
  }

  const boundaryChecks = [
    [!boundary.ordinary_chat_can_trigger_main_agent, "普通聊天意外开放 MainAgent"],
    [!boundary.project_doc_rag_in_ordinary_chat, "ProjectDocRAG 意外进入普通聊天"],
    [!boundary.shell_tools_exposed, "Shell 工具意外暴露"],
    [!boundary.arbitrary_file_write_allowed, "任意文件写入意外开放"],
    [!boundary.unregistered_db_write_allowed, "未注册数据库写入意外开放"],
    [boundary.owner_write_requires_approval, "主人写操作绕过审批"],
    [!boundary.multi_step_write_automation_allowed, "多步写自动化意外开放"],
    [!boundary.extra_qq_send_side_effect_allowed, "额外 QQ 发送副作用意外开放"],
  ] as const;
  const writeContractKnown = input.webWriteState !== "unknown";
  const checks = writeContractKnown
    ? [
        ...boundaryChecks,
        [
          input.webWriteState === "closed" ||
            input.webWriteState === "approval_only" ||
            input.webWriteState === "registered_actions",
          "网页写入超出审批安全合同",
        ] as const,
      ]
    : boundaryChecks;
  const violations = checks.filter(([passed]) => !passed).map(([, label]) => label);
  return {
    checkedCount: checks.length - violations.length,
    expectedCount: checks.length,
    violationLabels: violations,
  };
}

export function buildDashboardOverview(
  input: DashboardOverviewInput,
): DashboardOverviewViewModel {
  const nowMs = input.nowMs ?? Date.now();
  const staleAfterMs = input.staleAfterMs ?? 120_000;
  const unavailable = new Set(input.unavailableSources);
  const sourceKeys: DashboardSourceKey[] = [
    "overview",
    "diagnostics",
    "external_read",
    "reliability",
  ];
  const sources = sourceKeys.map((key) => {
    const generatedAt = sourceGeneratedAt(key, input);
    const available = Boolean(generatedAt) && !unavailable.has(key);
    return {
      key,
      label: SOURCE_LABELS[key],
      available,
      generatedAt,
      stale: available && isStaleTimestamp(generatedAt, nowMs, staleAfterMs),
    };
  });

  const attentionItems: DashboardAttentionItem[] = [];
  for (const source of sources) {
    if (!source.available) {
      attentionItems.push({
        id: `source:${source.key}`,
        tone: "neutral",
        title: `${source.label}暂不可用`,
        detail: "总体判断不会把缺失证据当作正常；可刷新后再次读取。",
        route: source.key === "overview" ? "/owner-console" : `/owner-console/${source.key.replace("_", "-")}`,
        actionLabel: "查看对应页面",
      });
    }
  }

  const staleSources = sources.filter((source) => source.stale);
  if (staleSources.length > 0) {
    attentionItems.push({
      id: "source:stale",
      tone: "neutral",
      title: `${staleSources.length} 个首页数据源已过期`,
      detail: `超过 ${Math.round(staleAfterMs / 60_000)} 分钟未生成新快照：${staleSources.map((source) => source.label).join("、")}。`,
      route: "/owner-console",
      actionLabel: "刷新概况",
    });
  }

  const security = buildSecurityPosture(input);
  if (security.violationLabels.length > 0) {
    attentionItems.push({
      id: "security:boundary",
      tone: "danger",
      title: `${security.violationLabels.length} 项安全边界异常`,
      detail: security.violationLabels.join("；"),
      route: "/owner-console/settings",
      actionLabel: "查看设置",
    });
  }

  const recent = input.reliability?.recent;
  const reliability = {
    failureOccurrences: recent?.failure_occurrence_count ?? 0,
    failureGroups: recent?.failure_group_count ?? 0,
    activeGroups:
      (recent?.state_counts.unresolved ?? 0) +
      (recent?.state_counts.recurring ?? 0),
    recoveredGroups: recent?.state_counts.recovered ?? 0,
    insufficientGroups: recent?.state_counts.insufficient_evidence ?? 0,
    topItem: topReliabilityItem(recent?.items ?? []),
  };
  const unresolved = recent?.state_counts.unresolved ?? 0;
  const recurring = recent?.state_counts.recurring ?? 0;
  if (unresolved > 0) {
    attentionItems.push({
      id: "reliability:unresolved",
      tone: "danger",
      title: `${unresolved} 个可靠性故障组尚未恢复`,
      detail: "已有结构化失败证据，但尚未发现后续成功证据。",
      route: "/owner-console/reliability",
      actionLabel: "查看故障证据",
    });
  }
  if (recurring > 0) {
    attentionItems.push({
      id: "reliability:recurring",
      tone: "warning",
      title: `${recurring} 个可靠性故障组反复发生`,
      detail: "同一结构化故障在恢复后再次出现，建议优先查看最近时间证据。",
      route: "/owner-console/reliability",
      actionLabel: "查看可靠性",
    });
  }
  if (reliability.insufficientGroups > 0) {
    attentionItems.push({
      id: "reliability:insufficient",
      tone: "neutral",
      title: `${reliability.insufficientGroups} 个故障组证据不足`,
      detail: "不能据此判断故障仍在持续或已经恢复。",
      route: "/owner-console/reliability",
      actionLabel: "查看证据范围",
    });
  }

  const failedDiagnosticSections = input.diagnostics
    ? DIAGNOSTIC_SECTIONS.filter((key) => !input.diagnostics?.[key].ok)
    : [];
  if (failedDiagnosticSections.length > 0) {
    attentionItems.push({
      id: "diagnostics:unreadable",
      tone: "warning",
      title: `${failedDiagnosticSections.length} 个诊断区块读取异常`,
      detail: `读取异常：${failedDiagnosticSections
        .map((key) => DIAGNOSTIC_SECTION_LABELS[key])
        .join("、")}。这表示快照区块无法读取，不直接等价于外部服务故障。`,
      route: "/owner-console/diagnostics",
      actionLabel: "查看诊断",
    });
  }

  if (input.externalRead?.enabled && !input.externalRead.executor_configured) {
    attentionItems.push({
      id: "external-read:not-ready",
      tone: "warning",
      title: "联网查询已开启但执行器未就绪",
      detail: "这里只判断本地配置装配，不会执行 Tavily 实时探测。",
      route: "/owner-console/external-read",
      actionLabel: "查看联网配置",
    });
  }

  const pendingApprovals = input.overview?.counters.pending_approvals ?? 0;
  if (pendingApprovals > 0) {
    attentionItems.push({
      id: "work:approvals",
      tone: "warning",
      title: `${pendingApprovals} 项主人审批待处理`,
      detail: "写操作不会在审批前执行；请进入审批详情核对工具、风险和参数。",
      route: "/owner-console/approvals?status=pending",
      actionLabel: "只看待审批",
    });
  }
  const awaitingApprovalTasks = input.overview?.counters.awaiting_approval_tasks ?? 0;
  if (awaitingApprovalTasks > 0) {
    attentionItems.push({
      id: "work:tasks-awaiting-approval",
      tone: "warning",
      title: `${awaitingApprovalTasks} 个任务正在等待审批`,
      detail: "这些任务必须先决定关联审批；审批未决定前不能从网页取消。",
      route: "/owner-console/tasks?status=pending&category=awaiting_approval",
      actionLabel: "只看等待审批任务",
    });
  }
  const ordinaryPendingTasks = input.overview?.counters.ordinary_pending_tasks ?? 0;
  if (ordinaryPendingTasks > 0) {
    attentionItems.push({
      id: "work:tasks-ordinary-pending",
      tone: "warning",
      title: `${ordinaryPendingTasks} 个普通任务待处理`,
      detail: "这些任务尚未进入审批或执行，可进入详情核对目标并决定是否取消。",
      route: "/owner-console/tasks?status=pending&category=ordinary_pending",
      actionLabel: "只看普通待处理",
    });
  }
  const stalePendingTasks = input.overview?.counters.stale_pending_tasks ?? 0;
  if (stalePendingTasks > 0) {
    attentionItems.push({
      id: "work:tasks-stale",
      tone: "warning",
      title: `${stalePendingTasks} 个旧任务残留待收口`,
      detail: "旧记录没有同步结束；可逐项查看证据，并在详情页取消收口，不会执行原工具。",
      route: "/owner-console/tasks?status=pending&category=stale_residual",
      actionLabel: "只看旧任务残留",
    });
  }
  for (const task of input.overview?.recent_tasks.filter((row) => row.status === "failed").slice(0, 2) ?? []) {
    attentionItems.push({
      id: `task:failed:${task.task_id}`,
      tone: "warning",
      title: `最近任务 #${task.task_id} 失败`,
      detail: task.result_preview || task.latest_event_summary || "任务详情中保留了受限失败摘要。",
      route: `/owner-console/tasks/${task.task_id}`,
      actionLabel: "查看任务详情",
    });
  }

  attentionItems.sort((left, right) => {
    const priority = ATTENTION_PRIORITY[left.tone] - ATTENTION_PRIORITY[right.tone];
    return priority !== 0 ? priority : left.id.localeCompare(right.id);
  });
  const actionableCount = attentionItems.filter((item) => item.tone !== "neutral").length;
  const availableSourceCount = sources.filter((source) => source.available).length;
  const staleSourceCount = staleSources.length;

  let overall: DashboardOverviewViewModel["overall"];
  if (security.violationLabels.length > 0 || unresolved > 0) {
    overall = {
      tone: "danger",
      label: "已降级",
      headline: "当前存在明确异常，需要主人优先查看",
      detail: `发现 ${security.violationLabels.length + unresolved} 项高优先级证据；判断仅基于已接入的只读快照。`,
    };
  } else if (actionableCount > 0) {
    overall = {
      tone: "warning",
      label: "需要关注",
      headline: `当前有 ${actionableCount} 项事项需要关注`,
      detail: `包括反复故障、待处理工作或区块读取异常；${availableSourceCount}/4 个数据源可读取。`,
    };
  } else if (
    availableSourceCount < sources.length ||
    staleSourceCount > 0 ||
    reliability.insufficientGroups > 0 ||
    input.reliability === null
  ) {
    overall = {
      tone: "neutral",
      label: "证据不足",
      headline: "当前没有明确待处理事项，但证据不足以证明持续健康",
      detail: `${availableSourceCount}/4 个数据源可读取，${staleSourceCount} 个快照已过期。`,
    };
  } else {
    overall = {
      tone: "success",
      label: "当前稳定",
      headline: "当前覆盖范围内未发现需要处理的事项",
      detail: "这表示已接入证据中没有未恢复或反复故障，不代表未接入组件持续在线。",
    };
  }

  return {
    overall,
    attentionItems,
    actionableCount,
    reliability,
    security,
    sources,
    availableSourceCount,
    staleSourceCount,
  };
}
