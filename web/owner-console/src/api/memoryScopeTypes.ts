export type MemoryMaintenanceScope = {
  bot_self_id: string;
  persona_id: string;
  persona_name: string;
  role_card_key: string;
  storage: string;
  database: string;
  session_namespace: string;
  revision: string;
};

export function sameMemoryScope(a: MemoryMaintenanceScope | null | undefined, b: MemoryMaintenanceScope | null | undefined): boolean {
  return Boolean(a && b && a.bot_self_id === b.bot_self_id && a.revision === b.revision);
}
