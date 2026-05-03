const BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}`
  : "";   // empty = use Next.js rewrites (proxied)

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as T;
}

export const api = {
  health: ()               => apiFetch<{ status: string }>("/api/health"),
  stats:  ()               => apiFetch<Stats>("/api/stats"),
  runs:   (limit = 20)     => apiFetch<{ runs: Run[]; total: number }>(`/api/runs?limit=${limit}`),
  getRun: (id: string)     => apiFetch<Run>(`/api/run/${id}`),
  tours:  (limit = 50)     => apiFetch<{ tours: Tour[]; total: number }>(`/api/tours?limit=${limit}`),
  getTour:(id: string)     => apiFetch<Tour>(`/api/tours/${id}`),
  evalLatest: ()           => apiFetch<EvalResult>("/api/eval/latest"),

  runSingle: (tour: TourRunPayload) =>
    apiFetch<{ run_id: string; status: string }>("/api/run", {
      method: "POST",
      body: JSON.stringify(tour),
    }),

  uploadExcel: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return fetch("/api/upload", { method: "POST", body: form }).then(r => r.json()) as Promise<UploadResult>;
  },

  runBatch: (upload_id: string, tour_ids?: string[]) =>
    apiFetch<{ run_ids: string[]; total: number }>("/api/batch", {
      method: "POST",
      body: JSON.stringify({ upload_id, tour_ids }),
    }),
};

// ── Types ──────────────────────────────────────────────────────────────────

export interface Stats {
  total_runs: number;
  completed: number;
  running: number;
  errors: number;
  avg_quality_score: number;
  total_cost_usd: number;
  avg_cost_per_tour: number;
}

export interface Run {
  run_id: string;
  tour_name: string;
  destination: string;
  status: "queued" | "running" | "complete" | "error";
  created_at: string;
  result?: RunResult;
}

export interface RunResult {
  quality_score: number;
  model_used: string;
  cost_usd: number;
  export_id?: string;
  stage_timings: Record<string, number>;
  generated: GeneratedContent;
  validation: { passed: number; failed: number; failed_rules: string[]; quality_score: number };
  raw_input: { description: string };
}

export interface GeneratedContent {
  title: string;
  tagline: string;
  description: string;
  highlights: string[];
  seo_meta_title: string;
  seo_meta_description: string;
}

export interface Tour {
  id: string;
  tour_name: string;
  destination: string;
  title: string;
  tagline: string;
  description: string;
  highlights: string;
  seo_meta_title: string;
  seo_meta_description: string;
  quality_score: number;
  model_used: string;
  cost_usd: number;
  is_active: boolean;
  created_at: string;
}

export interface UploadResult {
  upload_id: string;
  filename: string;
  valid: boolean;
  summary: string;
  col_map: Record<string, string>;
  missing_required: string[];
  tour_count: number;
  row_errors: string[];
  tours_preview: TourRunPayload[];
}

export interface TourRunPayload {
  tour_name: string;
  destination: string;
  duration_days: number;
  raw_description: string;
  highlights: string[];
  inclusions: string[];
  price_usd: number;
  supplier_name: string;
}

export interface EvalResult {
  available: boolean;
  aggregate?: {
    run_id: string;
    judge_score_avg: number;
    pipeline_score_avg: number;
    success_rate: number;
    total_cost_usd: number;
    dimension_averages: Record<string, number>;
  };
  results?: Array<{
    tour_name: string;
    destination: string;
    judge_scores: Record<string, number>;
    pipeline: { quality_score: number; cost_usd: number; model_used: string };
  }>;
}
