export type OwnerConsoleHealth = {
  ok: boolean;
  service: string;
  schema_version: string;
  api_prefix: string;
  read_only: boolean;
  http_api_enabled: boolean;
  web_write_enabled: boolean;
  enabled_routes: string[];
};

export type OwnerConsoleError = {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
};

export type OwnerConsoleEnvelope<TData> = {
  schema_version: string;
  read_model_schema_version: string;
  transport: "http";
  api_prefix: string;
  resource: string;
  generated_at: string;
  read_only: boolean;
  http_api_enabled: boolean;
  web_write_enabled: boolean;
  data: TData | null;
  error: OwnerConsoleError | null;
};

export type OwnerConsoleRouteRow = {
  name: string;
  resource: string;
  path: string;
  method: "GET";
  read_page: string;
  runtime_method: string;
  read_model: string;
  query_params: string[];
  path_params: string[];
  requires_context: boolean;
  read_only: boolean;
  http_api_enabled: boolean;
  web_write_enabled: boolean;
};

export type OwnerConsoleRouteContract = {
  api_prefix: string;
  allowed_methods: string[];
  context_override_allowed: boolean;
  write_routes_enabled: boolean;
  route_count: number;
  rows: OwnerConsoleRouteRow[];
  boundary: Record<string, boolean>;
};

export type OwnerConsoleRoutesEnvelope =
  OwnerConsoleEnvelope<OwnerConsoleRouteContract>;

export type OwnerConsoleSnapshot = {
  health: OwnerConsoleHealth | null;
  routes: OwnerConsoleRoutesEnvelope | null;
};
