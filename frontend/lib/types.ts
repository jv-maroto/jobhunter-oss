// Tipos del contrato API (sincronizados con ARCHITECTURE.md)

export type JobStatus =
  | "detected"
  | "prepared"
  | "applied"
  | "interviewing"
  | "offer"
  | "rejected"
  | "ghosted";

export type PersonStatus =
  | "pending"
  | "queued"
  | "sent"
  | "accepted"
  | "ignored";

export type PostStatus = "draft" | "scheduled" | "published";

export const JOB_TRACK_LABELS = {
  data_engineer: "Data Engineer",
  data_analyst: "Data Analyst",
  data_scientist: "Data Scientist",
  analytics_eng: "Analytics Engineer",
  bi: "Business Intelligence",
  ai_ml: "AI / Machine Learning",
  quant: "Quantitative Research / Development",
  dev: "Software Development",
  sysadmin: "Systems / DevOps",
} as const;
export type JobTrack = keyof typeof JOB_TRACK_LABELS;
export const EMPLOYMENT_LABELS = {
  permanent: "Permanent",
  temporary: "Temporary",
  contract: "Contract / freelance",
  internship: "Internship",
  apprenticeship: "Apprenticeship",
  full_time: "Full-time",
  part_time: "Part-time",
} as const;
export type EmploymentType = keyof typeof EMPLOYMENT_LABELS;
export type SalaryBand = "high" | "mid" | "low" | "unknown";

export interface QualificationAssessment {
  recommendation: "strong" | "consider" | "stretch" | "unlikely" | "unknown";
  summary: string;
  checks: {
    kind: "education" | "experience" | "skills" | "language";
    importance: "required" | "preferred" | "unclear";
    status: "met" | "gap" | "unknown";
    requirement: string;
    evidence: string | null;
  }[];
}

export interface Job {
  id: number;
  source: string;
  source_url: string;
  title: string;
  company: string;
  location: string;
  remote: boolean;
  employment_type?: EmploymentType | null;
  employment_compatible?: boolean | null;
  seniority_compatible?: boolean | null;
  salary_in_range?: boolean | null;
  remote_compatible?: boolean | null;
  location_compatible?: boolean | null;
  salary_min?: number;
  salary_max?: number;
  currency?: string;
  salary_period?: "year" | "month" | "week" | "day" | "hour" | null;
  posted_at: string;
  description: string;
  track: JobTrack;
  predicted_salary_band: SalaryBand;
  match_score: number;
  rejection_reason?: string;
  key_matches: string[];
  missing_skills: string[];
  personalization_hooks: string[];
  status: JobStatus;
  applied_at?: string;
  cv_path?: string;
  cover_letter_path?: string;
  created_at?: string;
  notes?: string | null;
  next_action?: string | null;
  next_action_at?: string | null;
  qualification_assessment?: QualificationAssessment | null;
}

export interface Person {
  id: number;
  full_name: string;
  headline: string;
  company?: string;
  profile_url: string;
  reason: string;
  message: string;
  status: PersonStatus;
  priority: number;
  created_at: string;
}

export type PostKind = "personal" | "trending";

export interface Post {
  id: number;
  date: string;
  topic: string;
  content: string;
  image_path?: string;
  hashtags: string[];
  status: PostStatus;
  kind: PostKind;
  source_url?: string;
  scheduled_at?: string;
  published_at?: string;
}

export interface Metrics {
  today: {
    new_jobs: number;
    jobs_above_70: number;
    applications_prepared: number;
    persons_to_connect: number;
    post_scheduled?: Post;
  };
  pipeline: Record<JobStatus, Job[]>;
  api_cost_eur: { today: number; month: number };
}

export interface PrepareApplicationResponse {
  application_id: number;
  job_id: number;
  cv_path: string;
  cover_letter_path: string;
  cv_content: string;
  cover_letter_content: string;
  language: string;
  cv_provenance: {
    mode: string;
    source_filename: string | null;
    sha256: string | null;
    language: string;
  };
}

export interface ApplicationReview {
  application_id: number | null;
  job: Job;
  status: string;
  provider: string | null;
  submitted_at: string | null;
  prepared_at: string | null;
  cv_url: string | null;
  cover_url: string | null;
  cv_source_filename: string | null;
  cover_letter_content: string | null;
}

export interface ApplicationsPage {
  total: number;
  items: ApplicationReview[];
}

export interface CompanyAggregate {
  /** Backend may send `name` (canonical) or `company` (legacy). */
  name?: string;
  company?: string;
  avg_score: number;
  /** Backend canonical is `jobs_count`; legacy was `jobs_detected`. */
  jobs_count?: number;
  jobs_detected?: number;
  internal_connections?: number;
  last_activity?: string | null;
  best_match?: Job;
}

export interface CommentSuggestion {
  id: number;
  post_url: string;
  post_author: string;
  post_excerpt: string;
  suggested_comment: string;
}

export type AiProvider = "anthropic" | "gemini" | "ollama" | "openai";

export interface ApiCostBreakdown {
  provider: AiProvider;
  calls_today: number;
  calls_month: number;
  cost_today_eur: number;
  cost_month_eur: number;
  avg_latency_ms: number;
}

export interface ApiCostCall {
  id: number;
  provider: AiProvider;
  model: string;
  endpoint: string;
  latency_ms: number;
  tokens_in: number;
  tokens_out: number;
  cost_eur: number;
  created_at: string;
  ok: boolean;
}

export interface ApiCosts {
  total_today_eur: number;
  total_month_eur: number;
  by_provider: ApiCostBreakdown[];
  recent_calls: ApiCostCall[];
  /** Coste diario (últimos 30 días) para el sparkline. */
  daily: { d: string; v: number }[];
}

export const JOB_STATUSES: JobStatus[] = [
  "detected",
  "prepared",
  "applied",
  "interviewing",
  "offer",
  "rejected",
  "ghosted",
];
