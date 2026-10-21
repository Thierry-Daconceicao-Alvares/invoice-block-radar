// Types of what the FastAPI service returns, and a server-side fetch helper.

export type Cause = "waiting_for_goods" | "likely_mismatch" | "routine_check";

export const CAUSES: Record<Cause, { label: string; short: string; tone: string }> = {
  likely_mismatch: { label: "Likely mismatch", short: "Buyer to fix", tone: "fix" },
  routine_check: { label: "Routine check", short: "Quick check", tone: "check" },
  waiting_for_goods: { label: "Waiting for goods", short: "Goods receipt", tone: "goods" },
};

export const RELEASE_REASONS: Record<string, string> = {
  released_after_review: "Released, nothing corrected",
  waiting_for_goods: "Goods arrived after the invoice",
  invoice_corrected: "Invoice cancelled or credited",
  order_corrected: "Order price or quantity changed",
};

export type Overview = {
  items: number;
  blocked_items: number;
  blocked_share: number;
  blocked_value_share: number;
  releases: { by_a_person: number; releases: number; people: number };
  release_reasons: {
    release_reason: string;
    blocks: number;
    released_by_a_person: number;
    median_days_blocked: number;
  }[];
  monthly_block_rate: { month: string; invoiced_lines: number; block_rate: number }[];
  variants: { items: number; distinct_paths: number; top_10_paths_share: number };
};

export type ProcessMap = {
  nodes: { activity: string; events: number; items: number }[];
  edges: { source: string; target: string; transitions: number; median_days: number }[];
};

export type Scores = Record<string, number>;

export type Evaluation = {
  forecast: {
    lines: Record<string, number>;
    block_rate_test: number;
    test_scores: Record<string, Scores>;
    validation_scores: Record<string, Scores>;
    drivers_mean_abs_shap: Record<string, number>;
  };
  forecast_curves: Record<string, [number, number][]>;
  triage: {
    blocks: Record<string, number>;
    correction_rate_test: number;
    test_scores: Record<string, Scores>;
    validation_scores: Record<string, Scores>;
    test_with_august_threshold: Record<string, number>;
  };
  triage_curves: Record<string, [number, number][]>;
  detective: {
    blocks: number;
    by_predicted_cause: Record<Cause, Record<string, number>>;
    corrections_sent_to_the_buyer: number;
    goods_waits_recognised: number;
    snapshot: { day: string; open_blocks: number };
  };
  writer: { model: string; notes: number; passed_all_checks: number; median_seconds: number; checks: string[] };
};

export type QueueItem = {
  case_id: string;
  po_document: string;
  vendor: string;
  spend_area: string;
  line_value_eur: number;
  blocked_on: string;
  days_open: number;
  cause: Cause;
  owner: string;
  priority: number;
  has_recorded_note: boolean;
};

export type Queue = {
  snapshot: string;
  total: number;
  by_cause: Record<Cause, { blocks: number; value_eur: number }>;
  items: QueueItem[];
};

export type CaseDetail = {
  case: {
    case_id: string;
    po_document: string;
    vendor: string;
    buyer: string;
    company: string;
    spend_area: string;
    line_value_eur: number;
    blocked_on: string;
    days_open: number;
    goods_received: boolean;
    cause: Cause;
    cause_text: string;
    owner: string;
    action: string;
    contact_vendor: boolean;
    vendor_blocks_before: number;
    vendor_corrections_before: number;
    buyer_blocks_before: number;
    buyer_corrections_before: number;
  };
  priority: number;
  score: number;
  outcome: { release_reason: string; days_blocked: number; released_by_a_person: boolean };
  note: { summary: string; next_step: string; email_subject: string | null; email_body: string | null };
  note_source: string;
  checks: string[];
};

export type ForecastOptions = {
  categories: Record<string, string[]>;
  vendors: string[];
  buyers: string[];
  examples: (Record<string, string | number | boolean | null> & { case_id: string; was_blocked: boolean })[];
};

export type ForecastResult = {
  risk: number;
  average_risk: number;
  times_average: number;
  band: "low" | "medium" | "high";
  reasons: { input: string; label: string; effect: number }[];
  history_as_of: string;
  history: Record<string, { paid_before: number; blocked_before: number }>;
};

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export async function getJSON<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { next: { revalidate: 3600 } });
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json() as Promise<T>;
}

export const fmt = {
  int: (n: number) => n.toLocaleString("en-GB"),
  pct: (share: number, digits = 0) => `${(share * 100).toFixed(digits)}%`,
  eur: (n: number) =>
    n >= 1_000_000 ? `€${(n / 1_000_000).toFixed(1)}M` : n >= 10_000 ? `€${Math.round(n / 1000)}k` : `€${n.toLocaleString("en-GB")}`,
};
