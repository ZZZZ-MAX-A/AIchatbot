import type {
  OwnerConsoleActionEnvelope,
  OwnerConsoleEnvelope,
} from "./ownerConsoleTypes";

export const OWNER_CONSOLE_HTTP_SCHEMA_VERSION = "owner_console.http.v1";
export const OWNER_CONSOLE_API_PREFIX = "/api/v1/owner-console";

export type ContractCheckResult = {
  ok: boolean;
  message: string;
};

export function checkOwnerConsoleEnvelope(
  envelope: OwnerConsoleEnvelope<unknown>,
): ContractCheckResult {
  if (envelope.schema_version !== OWNER_CONSOLE_HTTP_SCHEMA_VERSION) {
    return {
      ok: false,
      message: "接口版本与前端预期不一致",
    };
  }
  if (envelope.transport !== "http") {
    return {
      ok: false,
      message: "接口传输类型异常",
    };
  }
  if (envelope.api_prefix !== OWNER_CONSOLE_API_PREFIX) {
    return {
      ok: false,
      message: "接口前缀与前端预期不一致",
    };
  }
  if (envelope.read_only !== true) {
    return {
      ok: false,
      message: "只读模式未开启",
    };
  }
  if (envelope.http_api_enabled !== true) {
    return {
      ok: false,
      message: "HTTP 接口未开启",
    };
  }
  if (envelope.web_write_enabled !== false) {
    return {
      ok: false,
      message: "网页写入状态异常",
    };
  }
  return {
    ok: true,
    message: "接口契约正常",
  };
}

export function checkOwnerConsoleActionEnvelope(
  envelope: OwnerConsoleActionEnvelope<unknown>,
): ContractCheckResult {
  if (envelope.schema_version !== OWNER_CONSOLE_HTTP_SCHEMA_VERSION) {
    return { ok: false, message: "接口版本与前端预期不一致" };
  }
  if (
    envelope.transport !== "http" ||
    envelope.api_prefix !== OWNER_CONSOLE_API_PREFIX
  ) {
    return { ok: false, message: "手动诊断接口契约异常" };
  }
  if (
    envelope.read_only !== false ||
    envelope.manual_runtime_action !== true ||
    envelope.http_api_enabled !== true
  ) {
    return { ok: false, message: "手动诊断动作状态异常" };
  }
  if (
    envelope.web_write_enabled !== false ||
    envelope.configuration_write_enabled !== false ||
    envelope.business_data_write_enabled !== false
  ) {
    return { ok: false, message: "手动诊断写入边界异常" };
  }
  return { ok: true, message: "手动诊断接口契约正常" };
}
