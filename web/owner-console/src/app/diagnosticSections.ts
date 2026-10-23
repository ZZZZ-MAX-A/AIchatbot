import type {
  OwnerConsoleHealthSnapshot,
  OwnerConsoleTextSnapshotSection,
} from "../api/ownerConsoleTypes";

// One list governs the overview's failure detection and the diagnostic evidence.
const SECTION_SPECS = [
  { key: "bot_status", label: "Owner Console", attentionLabel: "Bot 状态" },
  { key: "diagnostics", label: "只读诊断边界", attentionLabel: "运行诊断" },
  { key: "config", label: "功能配置", attentionLabel: "配置" },
  { key: "vision", label: "视觉配置", attentionLabel: "图片识别" },
  { key: "image_cache", label: "图片缓存", attentionLabel: "图片缓存" },
  { key: "memory", label: "记忆与 RAG 统计", attentionLabel: "记忆" },
  { key: "tts", label: "语音配置", attentionLabel: "语音" },
  { key: "recent_errors", label: "近期错误取证", attentionLabel: "最近错误" },
] as const;

export type DiagnosticSection = {
  key: (typeof SECTION_SPECS)[number]["key"];
  label: string;
  attentionLabel: string;
  section: OwnerConsoleTextSnapshotSection;
};

export function diagnosticSections(snapshot: OwnerConsoleHealthSnapshot): DiagnosticSection[] {
  return SECTION_SPECS.map((spec) => ({ ...spec, section: snapshot[spec.key] }));
}
