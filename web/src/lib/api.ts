export type Severity = "critical" | "high" | "medium" | "low";
export type Flag = { severity: Severity; title: string; detail: string; rule?: string };
export type Concern = { severity: "high" | "medium" | "low"; title: string; detail: string; affected_count?: number };
export type Verdict = { verdict: "looks_right" | "concerns" | "dangerous"; headline: string; summary: string; concerns: Concern[]; fix_instructions?: string };
export type TableChange = {
  dropped: boolean; deleted: number; inserted: number; updated: number; rows_before: number; rows_after: number; changed_columns: string[];
  samples: { deleted: { rowid: number; before: Record<string, unknown> }[]; inserted: { rowid: number; after: Record<string, unknown> }[];
    updated: { rowid: number; before: Record<string, unknown>; after: Record<string, unknown>; changed: string[] }[] };
};
export type Consequences = {
  ok: boolean; error: { message: string; traceback?: string } | null; stdout?: string; logs?: string[]; duration_ms?: number;
  tables: Record<string, TableChange>; row_counts: Record<string, { before: number; after: number }>;
  payments: { count: number; total_cents: number; samples: { charge_id: number; amount_cents: number; reason: string }[] };
  emails: { count: number; samples: { to: string; subject: string; body: string }[] };
  blocked: { kind: string; target: string }[];
  guards: { env_keys?: string[]; uid?: number; hostname?: string; root_writable?: boolean };
  audit?: { emails?: { vip_count?: number; templated_count?: number }; refunds?: { over_refunded_count?: number } };
  sandbox: { id: string; runtime: string; network: string; memory: string; timeout_s: number; read_only_root: boolean; exit_code: number; killed: string | null; wall_ms: number; destroyed: boolean };
};
export type Attempt = { n: number; sandbox_id: string; code: string; summary: string; consequences: Consequences; flags: Flag[]; plan_sha256?: string; effects_sha256?: string | null; created_at?: number };
export type Approval = { approved_at: number; approver: string; plan_sha256: string; effects_sha256: string; sandbox_id: string; warnings: string[] };
export type RunEvent = { t: number; kind: string; title: string; detail: string };
export type RunStatus = "queued" | "planning" | "rehearsing" | "verifying" | "review" | "applying" | "applied" | "drifted" | "rejected" | "failed";
export type Run = {
  id: string; task: string; mode: "agent" | "manual"; status: RunStatus; created_at: number; events: RunEvent[]; attempts: Attempt[];
  verdict: Verdict | null; flags: Flag[]; final_message: string | null; error: string | null; agent_model: string; verifier_model: string; approval?: Approval | null; version?: number;
  apply_result: null | { rows_written?: number; refunds?: number; refund_total_cents?: number; emails_sent?: number; emails_failed?: number; drift_count?: number; drifted?: unknown[] };
};
export type Business = {
  name: string; counts: { customers: number; orders: number; charges: number; tickets: number };
  refunded: { count: number; total_cents: number }; recent_tickets: { id: number; customer: string; subject: string; created_at: string }[];
  beanpay: { count: number; total_cents: number };
};
export type RunSummary = {
  id: string; task: string; mode: "agent" | "manual"; status: RunStatus; created_at: number; attempts: number; verdict: Verdict["verdict"] | null;
  money_cents: number; emails: number; rows: number; blocked: boolean; plan_sha256: string | null; approval: Approval | null; apply_result: Run["apply_result"];
};
export type Health = { ok: boolean; inference_configured: boolean; sandbox_ready?: boolean; sandbox_status?: string; agent_model: string; verifier_model: string; sandbox_runtime: string; docker: string | null };

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
  business: () => req<Business>("/business"),
  createRun: (task: string) => req<{ id: string }>("/runs", { task }),
  createManualRun: (task: string, code: string) => req<{ id: string }>("/runs/manual", { task, code }),
  run: (id: string) => req<Run>(`/runs/${id}`),
  runs: () => req<RunSummary[]>("/runs"),
  fix: (id: string, note?: string) => req<{ id: string }>(`/runs/${id}/fix`, { note }),
  approve: (id: string, approver?: string) => req<Run>(`/runs/${id}/approve`, { approver }),
  reject: (id: string) => req<Run>(`/runs/${id}/reject`, {}),
  reset: () => req<Business>("/demo/reset", {}),
};

export const usd = (cents: number) => (cents / 100).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: cents % 100 ? 2 : 0 });
export const num = (n: number) => n.toLocaleString("en-US");
