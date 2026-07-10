import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = dirname(fileURLToPath(new URL("../package.json", import.meta.url)));
const srcRoot = join(projectRoot, "src");
const apiFile = join(srcRoot, "api", "ownerConsoleApi.ts");
const appFile = join(srcRoot, "app", "App.tsx");
const placeholderFile = join(srcRoot, "app", "PlaceholderPage.tsx");
const autoRefreshHookFile = join(srcRoot, "hooks", "useControlledAutoRefresh.ts");
const autoRefreshHookRelative = "src/hooks/useControlledAutoRefresh.ts";

const expectedStaticPaths = [
  "HEALTH_PATH",
  "`${API_BASE}/routes`",
  "`${API_BASE}/overview`",
  "`${API_BASE}/diagnostics`",
  "`${API_BASE}/memory`",
  "`${API_BASE}/access-control`",
  "`${API_BASE}/settings`",
  "`${API_BASE}/tasks`",
  "`${API_BASE}/approvals`",
];

const expectedApiMethods = [
  "getHealth",
  "getRoutes",
  "getOverview",
  "getDiagnostics",
  "getMemory",
  "getAccessControl",
  "getSettings",
  "getTasks",
  "getTaskDetail",
  "getApprovals",
  "getApprovalDetail",
];

const expectedPageRoutes = [
  "/owner-console",
  "/owner-console/tasks",
  "/owner-console/tasks/:task_id",
  "/owner-console/approvals",
  "/owner-console/approvals/:approval_id",
  "/owner-console/diagnostics",
  "/owner-console/memory",
  "/owner-console/access-control",
  "/owner-console/settings",
];

const forbiddenPathFragments = [
  "/openapi",
  "/docs",
  "/redoc",
];

const forbiddenApiNames = [
  "approveApproval",
  "rejectApproval",
  "resumeApproval",
  "createTask",
  "cancelTask",
  "retryTask",
  "saveSettings",
  "switchRoleCard",
  "updateAccessControl",
  "rebuildMemoryIndex",
  "runDiagnosticsProbe",
  "clearImageCache",
  "clearErrorLog",
  "addMemory",
  "deleteMemory",
];

const failures = [];

function normalizedRelative(path) {
  return relative(projectRoot, path).replaceAll("\\", "/");
}

function readText(path) {
  return readFileSync(path, "utf8");
}

function walk(path) {
  const result = [];
  for (const entry of readdirSync(path)) {
    const fullPath = join(path, entry);
    const stats = statSync(fullPath);
    if (stats.isDirectory()) {
      result.push(...walk(fullPath));
    } else if (/\.(ts|tsx)$/.test(entry)) {
      result.push(fullPath);
    }
  }
  return result;
}

function fail(message) {
  failures.push(message);
}

const sourceFiles = walk(srcRoot);
const sourceTexts = sourceFiles.map((path) => ({
  path,
  rel: normalizedRelative(path),
  text: readText(path),
}));

if (!existsSync(autoRefreshHookFile)) {
  fail("The controlled auto-refresh hook is missing.");
}

if (existsSync(placeholderFile)) {
  fail("PlaceholderPage.tsx still exists after all main pages have real data.");
}

const apiText = readText(apiFile);
const appText = readText(appFile);

const fetchLocations = sourceTexts
  .filter((file) => /\bfetch\s*\(/.test(file.text))
  .map((file) => file.rel);
if (fetchLocations.length !== 1 || fetchLocations[0] !== "src/api/ownerConsoleApi.ts") {
  fail(`fetch() must appear only in src/api/ownerConsoleApi.ts; found ${fetchLocations.join(", ") || "none"}.`);
}

for (const file of sourceTexts) {
  const methodMatches = file.text.matchAll(/\bmethod\s*:\s*["'`](\w+)["'`]/g);
  for (const match of methodMatches) {
    if (match[1] !== "GET") {
      fail(`${file.rel} uses HTTP method ${match[1]}; Owner Console frontend v0 must only use GET.`);
    }
  }

  for (const fragment of forbiddenPathFragments) {
    if (file.text.toLowerCase().includes(fragment)) {
      fail(`${file.rel} references forbidden path fragment ${fragment}.`);
    }
  }

  for (const name of forbiddenApiNames) {
    if (new RegExp(`\\b${name}\\b`).test(file.text)) {
      fail(`${file.rel} references forbidden write-style API name ${name}.`);
    }
  }

  if (/\bPlaceholderPage\b/.test(file.text)) {
    fail(`${file.rel} still references PlaceholderPage.`);
  }

  const isAutoRefreshTest = /useControlledAutoRefresh\.test\.[tj]sx?$/.test(
    file.rel,
  );
  if (
    file.rel !== autoRefreshHookRelative &&
    !isAutoRefreshTest &&
    /\b(?:setTimeout|clearTimeout)\s*\(/.test(file.text)
  ) {
    fail(`${file.rel} manages timers outside the controlled auto-refresh hook.`);
  }
  if (
    file.rel !== autoRefreshHookRelative &&
    !isAutoRefreshTest &&
    /\b(?:visibilityState|visibilitychange)\b/.test(file.text)
  ) {
    fail(`${file.rel} manages page visibility outside the controlled auto-refresh hook.`);
  }
  if (
    file.rel !== autoRefreshHookRelative &&
    /\bsetInterval\s*\(/.test(file.text)
  ) {
    fail(`${file.rel} uses setInterval outside the controlled auto-refresh hook.`);
  }
}

if (existsSync(autoRefreshHookFile)) {
  const autoRefreshHookText = readText(autoRefreshHookFile);
  for (const expectedToken of [
    "window.setTimeout",
    "window.clearTimeout",
    "document.visibilityState",
    'document.addEventListener("visibilitychange"',
    "AbortController",
  ]) {
    if (!autoRefreshHookText.includes(expectedToken)) {
      fail(`The controlled auto-refresh hook is missing ${expectedToken}.`);
    }
  }
  if (/\bsetInterval\s*\(/.test(autoRefreshHookText)) {
    fail("The first controlled auto-refresh implementation must not use setInterval.");
  }
}

for (const expectedPath of expectedStaticPaths) {
  if (!apiText.includes(expectedPath)) {
    fail(`ownerConsoleApi.ts allowlist is missing ${expectedPath}.`);
  }
}

for (const method of expectedApiMethods) {
  if (!new RegExp(`\\b${method}\\s*\\(`).test(apiText)) {
    fail(`ownerConsoleApi.ts is missing API client method ${method}().`);
  }
}

if (!apiText.includes("const taskDetailPrefix = `${API_BASE}/tasks/`;")) {
  fail("ownerConsoleApi.ts is missing task detail dynamic allowlist prefix.");
}

if (!apiText.includes("const approvalDetailPrefix = `${API_BASE}/approvals/`;")) {
  fail("ownerConsoleApi.ts is missing approval detail dynamic allowlist prefix.");
}

const positiveIntegerChecks = [...apiText.matchAll(/\^\[1-9\]\\d\*\$/g)].length;
if (positiveIntegerChecks < 2) {
  fail("ownerConsoleApi.ts must validate task and approval detail IDs as positive integers.");
}

for (const route of expectedPageRoutes) {
  if (!appText.includes(`path="${route}"`)) {
    fail(`App.tsx is missing route ${route}.`);
  }
}

if (failures.length > 0) {
  console.error("Owner Console frontend read-only guard failed:");
  for (const item of failures) {
    console.error(`- ${item}`);
  }
  process.exit(1);
}

console.log("Owner Console frontend read-only guard passed.");
console.log(`Checked ${sourceFiles.length} TypeScript source files.`);
console.log("Verified GET-only fetch usage, read-only allowlist, controlled timers, page routes, and absence of write-style API names.");
