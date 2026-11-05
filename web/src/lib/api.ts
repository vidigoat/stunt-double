export type Severity = "critical" | "high" | "medium" | "low";
export type Flag = { severity: Severity; title: string; detail: string; rule?: string };
export type Concern = { severity: "high" | "medium" | "low"; title: string; detail: string; affected_count?: number };
export type Verdict = { verdict: "looks_right" | "concerns" | "dangerous"; headline: string; summary: string; concerns: Concern[]; fix_instructions?: string; rule?: { title: string; sql: string }; cached?: { at: number; ms: number };
  jury?: { votes: { model: string; lab: string; verdict: "looks_right" | "concerns" | "dangerous" | null; headline: string; role: "verifier" | "juror" }[]; agree: number; cast: number } };
export type TableChange = {
  dropped: boolean; schema_changed?: boolean; deleted: number; inserted: number; updated: number; rows_before: number; rows_after: number; changed_columns: string[];
  samples: { deleted: { rowid: number; before: Record<string, unknown> }[]; inserted: { rowid: number; after: Record<string, unknown> }[];
    updated: { rowid: number; before: Record<string, unknown>; after: Record<string, unknown>; changed: string[] }[] };
};
export type Provenance = { status: "proven" | "unexplained" | "unavailable" | "derived"; statements?: number; writing_statements?: number;
  rows_measured?: number; rows_explained?: number; unexplained?: number; patterns?: number; deciders?: number; claimed_but_not_measured?: number; failed_on_replay?: number; reason?: string | null };
export type ProvenanceDetail = { summary: Provenance; statements: { i: number; rows: number; tables: Record<string, number>; sql: string }[];
  patterns?: { shape: string; rows: number; statements: number; first: number; example: string }[]; deciders?: { i: number; rows: number; sql: string }[];
  unexplained: { table: string; rowid: number; op: string }[]; claimed_only?: { table: string; rowid: number; op: string }[]; failed?: { i: number; error: string }[] };
export type GraphSummary = { nodes: number; by_kind: Record<string, number>; units: number; largest_unit: number; edges: number; hubs: number; truncated: boolean };
export type Consequences = {
  provenance?: Provenance; graph?: GraphSummary;
  ok: boolean; error: { message: string; traceback?: string } | null; stdout?: string; logs?: string[]; duration_ms?: number;
  tables: Record<string, TableChange>; row_counts: Record<string, { before: number; after: number }>;
  payments: { count: number; total_cents: number; samples: { charge_id: number; amount_cents: number; reason: string }[] };
  emails: { count: number; samples: { to: string; subject: string; body: string }[] };
  http?: { count: number; samples: { method: string; url: string; host: string; json: unknown; headers: Record<string, string> }[] };
  irreversible?: { refunds: number; refund_total_cents: number; emails: number; http: number; servers_deleted?: number };
  cloud?: CloudConsequences;
  browser?: { steps: { n: number; action: string; target: string; url: string; shot: string | null }[] };
  blocked: { kind: string; target: string }[];
  guards: { env_keys?: string[]; uid?: number; hostname?: string; root_writable?: boolean };
  audit?: { emails?: { vip_count?: number; templated_count?: number }; refunds?: { over_refunded_count?: number } };
  sandbox: { id: string; runtime: string; network: string; memory: string; timeout_s: number; read_only_root: boolean; exit_code: number; killed: string | null; wall_ms: number; destroyed: boolean };
};
export type CloudServer = { id: string; label: string; plan: string; region: string; monthly_cost_cents: number; tags: string[]; production: boolean;
  cpu_avg_7d: number; requests_7d: number; purpose: string; status: string };
export type CloudConsequences = { servers_before: number; servers_after: number; deleted: CloudServer[]; stopped: CloudServer[];
  resized: (CloudServer & { from_plan: string; from_cost_cents: number })[]; monthly_cost_before_cents: number; monthly_cost_after_cents: number;
  monthly_savings_cents: number; production_touched: string[]; fleet: CloudServer[]; calls: { method: string; path: string }[] };
export type Attempt = { n: number; sandbox_id: string; code: string; summary: string; consequences: Consequences; flags: Flag[]; plan_sha256?: string; effects_sha256?: string | null; created_at?: number; surgical_of?: number;
  approvals_required?: number; approval_reasons?: string[] };
export type Approval = { approved_at: number; approver: string; approvers?: string[]; notes?: string[]; plan_sha256: string; effects_sha256: string; sandbox_id: string; warnings: string[] };
export type RunEvent = { t: number; kind: string; title: string; detail: string };
export type RunStatus = "queued" | "planning" | "rehearsing" | "verifying" | "review" | "applying" | "applied" | "drifted" | "rejected" | "failed";
export type Run = {
  id: string; task: string; mode: "agent" | "manual" | "rollback"; status: RunStatus; approvals?: { name: string; at: number }[]; rollback_of?: string; rolled_back_by?: string; rollback_run?: string; created_at: number; events: RunEvent[]; attempts: Attempt[];
  verdict: Verdict | null; flags: Flag[]; final_message: string | null; error: string | null; agent_model: string; verifier_model: string; approval?: Approval | null; version?: number;
  rejection?: { by: string; at: number; reason: string } | null;
  promoted_rule?: string;
  surgical?: Surgical;
  apply_result: null | { rows_written?: number; refunds?: number; refund_total_cents?: number; emails_sent?: number; emails_failed?: number; http_delivered?: number; http_failed?: number; drift_count?: number; drifted?: unknown[]; error?: string };
};
export type SurgicalCounts = { rows: number; refunds: number; money_cents: number; emails: number; api_calls: number };
export type SurgicalOffer = { check_title: string; units_total: number; units_kept: number; units_dropped: number; flagged_rows: number;
  kept: SurgicalCounts; dropped: SurgicalCounts; dropped_units: number[]; caused_by?: { i: number; rows: number; how?: "chose" | "wrote" }[] };
export type Surgical = { offer?: SurgicalOffer; check?: { title: string; source: string }; none?: string; applied_to?: number };
export type Workspace = { id: string; name: string; kind: "demo" | "upload" | "vultr" | "postgres"; description: string };
export type Business = {
  name: string; workspace?: string; tables?: Record<string, number>; counts: Record<string, number>;
  refunded: { count: number; total_cents: number }; recent_tickets: { id: number; customer: string; subject: string; created_at: string }[];
  beanpay: { count: number; total_cents: number };
};
export type RunSummary = {
  id: string; task: string; mode: "agent" | "manual" | "rollback"; status: RunStatus; approvals?: { name: string; at: number }[]; rollback_of?: string; rolled_back_by?: string; rollback_run?: string; created_at: number; attempts: number; verdict: Verdict["verdict"] | null;
  money_cents: number; emails: number; rows: number; blocked: boolean; plan_sha256: string | null; approval: Approval | null; apply_result: Run["apply_result"];
};
export type Health = { ok: boolean; inference_configured: boolean; sandbox_ready?: boolean; sandbox_status?: string; agent_model: string; verifier_model: string; sandbox_runtime: string; docker: string | null; vm_isolation?: boolean; vm_plan?: string | null; sample_postgres?: boolean };

async function req<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { detail?: string }).detail || `Request failed (${res.status})`);
  return data as T;
}

export const api = {
  health: () => req<Health>("/health"),
  business: (ws = "demo") => req<Business>(`/business?ws=${encodeURIComponent(ws)}`),
  createRun: (task: string, workspace = "demo") => req<{ id: string }>("/runs", { task, workspace }),
  createManualRun: (task: string, code: string, workspace = "demo", isolation: "container" | "vultr_vm" = "container") =>
    req<{ id: string }>("/runs/manual", { task, code, workspace, isolation }),
  workspaces: () => req<{ workspaces: Workspace[] }>("/workspaces"),
  uploadWorkspace: async (name: string, file: File) => {
    const res = await fetch(`/api/workspaces?name=${encodeURIComponent(name)}`, { method: "POST", body: file, headers: { "Content-Type": "application/octet-stream" } });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error((data as { detail?: string }).detail || "Upload failed");
    return data as Workspace;
  },
  importSamplePostgres: () => req<Workspace>("/workspaces/postgres/sample", {}),
  importPostgres: (url: string, schema_name = "public", name = "My Postgres") => req<Workspace>("/workspaces/postgres", { url, schema_name, name }),
  importVultr: (api_key: string, name = "My Vultr fleet") => req<Workspace & { servers: number; monthly_cost_cents: number }>("/workspaces/vultr", { api_key, name }),
  deleteWorkspace: async (id: string) => {
    const res = await fetch(`/api/workspaces/${encodeURIComponent(id)}`, { method: "DELETE" });
    if (!res.ok) throw new Error(((await res.json().catch(() => ({}))) as { detail?: string }).detail || "Delete failed");
  },
  run: (id: string) => req<Run>(`/runs/${id}`),
  runs: () => req<RunSummary[]>("/runs"),
  fix: (id: string, note?: string) => req<{ id: string }>(`/runs/${id}/fix`, { note }),
  recheck: (id: string) => req<{ id: string }>(`/runs/${id}/recheck`, {}),
  provenance: (id: string, attempt = 0) => req<ProvenanceDetail>(`/runs/${id}/provenance?attempt=${attempt}`),
  surgical: (id: string) => req<{ id: string; offer: SurgicalOffer }>(`/runs/${id}/surgical`, {}),
  promote: (id: string, by?: string) => req<{ id: string; title: string; sql: string }>(`/runs/${id}/promote`, { by }),
  approve: (id: string, approver?: string, note?: string) => req<Run>(`/runs/${id}/approve`, { approver, note: note || undefined }),
  reject: (id: string, approver?: string, reason?: string) => req<Run>(`/runs/${id}/reject`, { approver, reason: reason || undefined }),
  rollback: (id: string) => req<{ id: string }>(`/runs/${id}/rollback`, {}),
  reset: () => req<Business>("/demo/reset", {}),
};

export const usd = (cents: number) => (cents / 100).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: cents % 100 ? 2 : 0 });
export const num = (n: number) => n.toLocaleString("en-US");
