// Tipos compartidos entre la extensión y el backend.
// Mantener sincronizados con jobhunter/backend (Pydantic models)
// y con frontend (Next.js dashboard).

export type JobStatus =
  | "detected"
  | "prepared"
  | "applied"
  | "interviewing"
  | "offer"
  | "rejected"
  | "ghosted";

export type PersonStatus = "pending" | "queued" | "sent" | "accepted" | "ignored";
export type PostStatus = "draft" | "scheduled" | "published";

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

export interface Post {
  id: number;
  date: string;
  topic: string;
  content: string;
  image_path?: string;
  hashtags: string[];
  status: PostStatus;
  scheduled_at?: string;
  published_at?: string;
}

// ---------------------------------------------------------------------------
// Tasks que envía el backend a la extensión (GET /ext/tasks)
// ---------------------------------------------------------------------------

export type ExtTaskType =
  | "connect_person"
  | "schedule_post"
  | "read_inbox"
  | "suggest_comments";

export interface ConnectPersonTask {
  id: string;                  // uuid de la tarea
  type: "connect_person";
  person_id: number;
  profile_url: string;
  message: string;
  priority?: number;
}

export interface SchedulePostTask {
  id: string;
  type: "schedule_post";
  post_id: number;
  content: string;
  scheduled_at: string;        // ISO 8601
  image_url?: string;          // opcional, servido por el backend
  hashtags?: string[];
}

export interface ReadInboxTask {
  id: string;
  type: "read_inbox";
}

export interface SuggestCommentsTask {
  id: string;
  type: "suggest_comments";
}

export type ExtTask =
  | ConnectPersonTask
  | SchedulePostTask
  | ReadInboxTask
  | SuggestCommentsTask;

export interface ExtTasksResponse {
  tasks: ExtTask[];
}

// ---------------------------------------------------------------------------
// Reportes que la extensión envía al backend
// ---------------------------------------------------------------------------

export interface ConnectResult {
  task_id: string;
  person_id: number;
  success: boolean;
  error?: string;
  executed_at: string;
}

export interface InboxMessage {
  thread_id: string;
  sender_name: string;
  sender_url?: string;
  preview: string;
  received_at?: string;
  unread: boolean;
}

export interface InboxReport {
  task_id?: string;
  messages: InboxMessage[];
  collected_at: string;
}

export interface InboxSuggestionsResponse {
  thread_id: string;
  suggestions: string[];       // hasta 3 respuestas
}

// ---------------------------------------------------------------------------
// Mensajes internos (background <-> content script <-> popup)
// ---------------------------------------------------------------------------

export type RuntimeMessage =
  | { type: "CONNECT_WITH_NOTE"; task: ConnectPersonTask }
  | { type: "SCHEDULE_POST"; task: SchedulePostTask }
  | { type: "READ_INBOX"; task: ReadInboxTask }
  | { type: "SUGGEST_COMMENTS"; task: SuggestCommentsTask }
  | { type: "PING_STATUS" }
  | { type: "FORCE_POLL" }
  | { type: "GET_PROFILE" }
  | { type: "GENERATE_COMMENT_FOR_POST"; payload?: unknown }
  | { type: "SEND_FEED_POSTS"; posts?: unknown[] }
  | { type: "DEBUG_SCAN_FEED" };

export interface RuntimeResponse {
  success: boolean;
  data?: unknown;
  error?: string;
}

// ---------------------------------------------------------------------------
// Settings persistidos en chrome.storage.local
// ---------------------------------------------------------------------------

export type SimSpeed = "slow" | "normal" | "fast";

export interface ExtSettings {
  backend_url: string;
  dashboard_url: string;
  sim_speed: SimSpeed;
  auto_execute: boolean;
  poll_interval_seconds: number;
}

export const DEFAULT_SETTINGS: ExtSettings = {
  backend_url: "http://localhost:8000",
  dashboard_url: "http://localhost:3000",
  sim_speed: "normal",
  auto_execute: false,
  poll_interval_seconds: 30
};
