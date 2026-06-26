// Mock data — usado cuando el backend no responde (fallback) y como
// seed inicial para desarrollo offline.

import type {
  ApiCostCall,
  ApiCosts,
  CommentSuggestion,
  CompanyAggregate,
  Job,
  Metrics,
  Person,
  Post,
} from "@/lib/types";

const now = new Date();
const iso = (d: Date) => d.toISOString();
const daysAgo = (n: number) => {
  const d = new Date(now);
  d.setDate(d.getDate() - n);
  return d;
};
const daysFromNow = (n: number) => {
  const d = new Date(now);
  d.setDate(d.getDate() + n);
  return d;
};

export const mockJobs: Job[] = [
  {
    id: 1,
    source: "linkedin",
    source_url: "https://www.linkedin.com/jobs/view/3920000001",
    title: "Senior Python Developer (Remote EU)",
    company: "Hetzner Cloud",
    location: "Remote · EU",
    remote: true,
    salary_min: 55000,
    salary_max: 72000,
    currency: "EUR",
    posted_at: iso(daysAgo(0)),
    description:
      "Build distributed services on Python 3.12, FastAPI, asyncio, Postgres and Redis. Bonus: pgvector, AI integrations.",
    match_score: 94,
    key_matches: ["Python 3.12", "FastAPI", "PostgreSQL", "Redis", "Docker"],
    missing_skills: ["Kubernetes operator"],
    status: "detected",
  },
  {
    id: 2,
    source: "remoteok",
    source_url: "https://remoteok.com/remote-jobs/python-ai-engineer-acme-2",
    title: "Python + AI Engineer",
    company: "Acme AI",
    location: "Remote · Worldwide",
    remote: true,
    salary_min: 40000,
    salary_max: 55000,
    currency: "EUR",
    posted_at: iso(daysAgo(0)),
    description:
      "Anthropic + Ollama, prompt engineering, RAG. Looking for a backend engineer who likes shipping.",
    match_score: 88,
    key_matches: ["Anthropic SDK", "Ollama", "FastAPI", "embeddings"],
    missing_skills: ["LangChain"],
    status: "detected",
  },
  {
    id: 3,
    source: "remotive",
    source_url: "https://remotive.com/remote-jobs/backend/fullstack-3",
    title: "Full-Stack Engineer (Python + React)",
    company: "Lumen Labs",
    location: "Remote · EU only",
    remote: true,
    salary_min: 38000,
    salary_max: 48000,
    currency: "EUR",
    posted_at: iso(daysAgo(1)),
    description:
      "FastAPI backend + React 19 frontend. SSE, websockets, modern toolchain.",
    match_score: 82,
    key_matches: ["FastAPI", "React 19", "TypeScript", "Tailwind"],
    missing_skills: ["GraphQL"],
    status: "detected",
  },
  {
    id: 4,
    source: "tecnoempleo",
    source_url: "https://www.tecnoempleo.com/oferta/4",
    title: "Backend Developer (Python) — Híbrido Tenerife",
    company: "Canary Tech Group",
    location: "Santa Cruz de Tenerife",
    remote: false,
    salary_min: 32000,
    salary_max: 38000,
    currency: "EUR",
    posted_at: iso(daysAgo(1)),
    description:
      "Backend en Django + FastAPI para una solución de gestión local.",
    match_score: 76,
    key_matches: ["Django", "FastAPI", "PostgreSQL"],
    missing_skills: ["Java"],
    status: "detected",
  },
  {
    id: 5,
    source: "linkedin",
    source_url: "https://www.linkedin.com/jobs/view/3920000005",
    title: "Junior Java Developer",
    company: "Random Corp",
    location: "Madrid",
    remote: false,
    salary_min: 22000,
    salary_max: 26000,
    currency: "EUR",
    posted_at: iso(daysAgo(2)),
    description: "Java 8, JSP, Struts. Onsite Madrid.",
    match_score: 22,
    rejection_reason: "Stack mismatch + onsite Madrid",
    key_matches: [],
    missing_skills: ["Java", "Struts"],
    status: "rejected",
  },
  {
    id: 6,
    source: "remoteok",
    source_url: "https://remoteok.com/remote-jobs/devops-6",
    title: "DevOps Engineer (Docker, K8s)",
    company: "ShipFast",
    location: "Remote · EU",
    remote: true,
    salary_min: 45000,
    salary_max: 60000,
    currency: "EUR",
    posted_at: iso(daysAgo(2)),
    description: "Docker, Kubernetes, GitHub Actions, Linux sysadmin.",
    match_score: 71,
    key_matches: ["Docker", "Linux", "GitHub Actions", "Bash"],
    missing_skills: ["Kubernetes prod"],
    status: "prepared",
    cv_path: "/tmp/cv_javier_shipfast.pdf",
    cover_letter_path: "/tmp/cover_shipfast.pdf",
  },
  {
    id: 7,
    source: "linkedin",
    source_url: "https://www.linkedin.com/jobs/view/3920000007",
    title: "Backend Engineer — FinTech",
    company: "Numeris",
    location: "Remote · EU",
    remote: true,
    salary_min: 50000,
    salary_max: 65000,
    currency: "EUR",
    posted_at: iso(daysAgo(3)),
    description: "FastAPI + Stripe + Postgres. SaaS billing platform.",
    match_score: 84,
    key_matches: ["FastAPI", "Stripe", "PostgreSQL"],
    missing_skills: [],
    status: "applied",
    applied_at: iso(daysAgo(1)),
    cv_path: "/tmp/cv_numeris.pdf",
    cover_letter_path: "/tmp/cover_numeris.pdf",
  },
  {
    id: 8,
    source: "linkedin",
    source_url: "https://www.linkedin.com/jobs/view/3920000008",
    title: "Senior Backend (Python)",
    company: "Vinted",
    location: "Remote · EU",
    remote: true,
    salary_min: 65000,
    salary_max: 85000,
    currency: "EUR",
    posted_at: iso(daysAgo(5)),
    description: "Marketplace backend. Python + Kafka.",
    match_score: 79,
    key_matches: ["Python", "Postgres", "Redis"],
    missing_skills: ["Kafka"],
    status: "interviewing",
    applied_at: iso(daysAgo(4)),
  },
  {
    id: 9,
    source: "remotive",
    source_url: "https://remotive.com/remote-jobs/backend/9",
    title: "Backend Developer — EdTech",
    company: "BrightPath",
    location: "Remote · Worldwide",
    remote: true,
    salary_min: 35000,
    salary_max: 50000,
    currency: "EUR",
    posted_at: iso(daysAgo(6)),
    description: "Django + DRF. Education platform.",
    match_score: 73,
    key_matches: ["Django", "DRF"],
    missing_skills: [],
    status: "ghosted",
    applied_at: iso(daysAgo(15)),
  },
  {
    id: 10,
    source: "linkedin",
    source_url: "https://www.linkedin.com/jobs/view/3920000010",
    title: "Python Engineer — AI Tooling",
    company: "Anthropic-adjacent Startup",
    location: "Remote · EU",
    remote: true,
    salary_min: 60000,
    salary_max: 80000,
    currency: "EUR",
    posted_at: iso(daysAgo(8)),
    description: "Tooling around LLMs, observability.",
    match_score: 91,
    key_matches: ["Anthropic SDK", "Python", "FastAPI", "Observability"],
    missing_skills: [],
    status: "offer",
    applied_at: iso(daysAgo(7)),
  },
];

export const mockPersons: Person[] = [
  {
    id: 1,
    full_name: "Laura Pérez Sánchez",
    headline: "Senior Recruiter — Hetzner Cloud",
    company: "Hetzner Cloud",
    profile_url: "https://www.linkedin.com/in/laura-perez-sanchez",
    reason: "Recruiter at top match company (Hetzner Cloud, score 94)",
    message:
      "Hola Laura, he visto la oferta de Senior Python Developer en Hetzner. Tengo experiencia construyendo APIs con FastAPI/Postgres/Redis (FitDash, SportEvent) y me encajaría muchísimo. ¿Tienes 5 min esta semana?",
    status: "pending",
    priority: 95,
    created_at: iso(daysAgo(0)),
  },
  {
    id: 2,
    full_name: "Markus Vogel",
    headline: "CTO @ Acme AI · Anthropic / Ollama",
    company: "Acme AI",
    profile_url: "https://www.linkedin.com/in/markus-vogel",
    reason: "CTO at high-match AI company (88)",
    message:
      "Hi Markus, I've been building Python + Anthropic SDK projects (FitDash uses Qwen 2.5 + Whisper). Would love to hear more about Acme AI's stack.",
    status: "pending",
    priority: 88,
    created_at: iso(daysAgo(0)),
  },
  {
    id: 3,
    full_name: "Sofía Ramos",
    headline: "Engineering Manager — Lumen Labs",
    company: "Lumen Labs",
    profile_url: "https://www.linkedin.com/in/sofia-ramos",
    reason: "EM in EU remote company (82)",
    message:
      "Hola Sofía, vi la oferta de Full-Stack en Lumen. Trabajo con FastAPI + React 19 + Tailwind v4 (SportEvent es mi TFG). Encantado de conectar.",
    status: "pending",
    priority: 82,
    created_at: iso(daysAgo(0)),
  },
  {
    id: 4,
    full_name: "James O'Connor",
    headline: "Tech Recruiter — Remote EU companies",
    profile_url: "https://www.linkedin.com/in/james-oconnor",
    reason: "Recruiter signal — posts about Python jobs weekly",
    message:
      "Hi James, I'm a Full-Stack Python + AI engineer (Mid) looking for remote EU roles in the 32–42k€ range. Would love to be on your radar.",
    status: "sent",
    priority: 70,
    created_at: iso(daysAgo(1)),
  },
];

export const mockPosts: Post[] = Array.from({ length: 7 }, (_, i) => {
  const d = daysFromNow(i);
  const topics = [
    "Cómo monté FitDash con Ollama (Qwen 2.5) + Whisper",
    "Por qué uso Typst en vez de LaTeX para CVs generados con IA",
    "FastAPI + APScheduler: scheduler casero sin Celery",
    "pgvector vs Pinecone: cuándo merece la pena cada uno",
    "Mi setup de scraping ético (rate limits + jobspy)",
    "De SysAdmin a Full-Stack en 18 meses: roadmap real",
    "Anthropic SDK + caching = -40% coste API",
  ];
  return {
    id: i + 1,
    date: iso(d),
    topic: topics[i],
    content: `# ${topics[i]}\n\nDraft del post para LinkedIn. Estructura: gancho → desarrollo → 3 bullets accionables → CTA.\n\nLorem ipsum dolor sit amet — este es el contenido del post que se publicará el ${d.toLocaleDateString("es-ES")}.`,
    image_path: undefined,
    hashtags: ["#Python", "#FastAPI", "#AI", "#OpenToWork"],
    status: i === 0 ? "scheduled" : "draft",
    scheduled_at: i === 0 ? iso(d) : undefined,
  };
});

export const mockMetrics: Metrics = {
  today: {
    new_jobs: mockJobs.filter((j) => {
      const d = new Date(j.posted_at);
      const today = new Date();
      return (
        d.getDate() === today.getDate() &&
        d.getMonth() === today.getMonth() &&
        d.getFullYear() === today.getFullYear()
      );
    }).length,
    jobs_above_70: mockJobs.filter((j) => j.match_score >= 70).length,
    applications_prepared: mockJobs.filter((j) => j.status === "prepared")
      .length,
    persons_to_connect: mockPersons.filter((p) => p.status === "pending").length,
    post_scheduled: mockPosts[0],
  },
  pipeline: {
    detected: mockJobs.filter((j) => j.status === "detected"),
    prepared: mockJobs.filter((j) => j.status === "prepared"),
    applied: mockJobs.filter((j) => j.status === "applied"),
    interviewing: mockJobs.filter((j) => j.status === "interviewing"),
    offer: mockJobs.filter((j) => j.status === "offer"),
    rejected: mockJobs.filter((j) => j.status === "rejected"),
    ghosted: mockJobs.filter((j) => j.status === "ghosted"),
  },
  api_cost_eur: { today: 0.42, month: 7.31 },
};

export const mockCompanies: CompanyAggregate[] = [
  {
    company: "Hetzner Cloud",
    avg_score: 94,
    jobs_detected: 1,
    internal_connections: 1,
    last_activity: iso(daysAgo(0)),
  },
  {
    company: "Anthropic-adjacent Startup",
    avg_score: 91,
    jobs_detected: 1,
    internal_connections: 0,
    last_activity: iso(daysAgo(7)),
  },
  {
    company: "Acme AI",
    avg_score: 88,
    jobs_detected: 1,
    internal_connections: 1,
    last_activity: iso(daysAgo(0)),
  },
  {
    company: "Numeris",
    avg_score: 84,
    jobs_detected: 1,
    internal_connections: 0,
    last_activity: iso(daysAgo(1)),
  },
  {
    company: "Lumen Labs",
    avg_score: 82,
    jobs_detected: 1,
    internal_connections: 1,
    last_activity: iso(daysAgo(0)),
  },
  {
    company: "Vinted",
    avg_score: 79,
    jobs_detected: 1,
    internal_connections: 0,
    last_activity: iso(daysAgo(4)),
  },
  {
    company: "Canary Tech Group",
    avg_score: 76,
    jobs_detected: 1,
    internal_connections: 0,
    last_activity: iso(daysAgo(1)),
  },
];

export const mockComments: CommentSuggestion[] = Array.from({ length: 10 }, (_, i) => ({
  id: i + 1,
  post_url: `https://www.linkedin.com/feed/update/urn:li:activity:${7245000000000000000 + i}`,
  post_author: [
    "Allie K. Miller",
    "Santiago Valdarrama",
    "Eduardo Manchón",
    "Pablo Yabo",
    "Lenny Rachitsky",
    "David Bonilla",
    "Andrej Karpathy",
    "Simon Willison",
    "Anthropic",
    "Vercel",
  ][i],
  post_excerpt:
    "Post sobre tendencias de Python/AI en producción y la próxima ola de developer tooling con LLMs locales...",
  suggested_comment:
    "Coincido — añadiría que con Ollama + Qwen 2.5 puedes correr esto local sin pagar API. Lo monté en FitDash y para texto + ASR va sobrado.",
}));

// Serie histórica para charts en /metrics
export const mockJobsPerDay = Array.from({ length: 30 }, (_, i) => {
  const d = daysAgo(29 - i);
  return {
    date: d.toLocaleDateString("es-ES", { day: "2-digit", month: "short" }),
    detected: Math.floor(Math.random() * 12) + 3,
    high_match: Math.floor(Math.random() * 6),
  };
});

export const mockAppsBySource = [
  { source: "linkedin", count: 18 },
  { source: "remoteok", count: 9 },
  { source: "remotive", count: 6 },
  { source: "tecnoempleo", count: 4 },
  { source: "weworkremotely", count: 2 },
];

// ── API cost tracking (multi-provider router) ──────────────────────────
const apiEndpoints = [
  "/jobs/score",
  "/jobs/prepare-application",
  "/persons/suggest-message",
  "/posts/generate-week",
  "/companies/enrich",
];
const apiProviders: Array<{
  provider: ApiCostCall["provider"];
  model: string;
  costPerCall: number;
  latency: number;
}> = [
  { provider: "anthropic", model: "claude-opus-4-7", costPerCall: 0.0185, latency: 1850 },
  { provider: "anthropic", model: "claude-sonnet-4-7", costPerCall: 0.0064, latency: 900 },
  { provider: "gemini", model: "gemini-2.5-pro", costPerCall: 0.0042, latency: 1100 },
  { provider: "ollama", model: "qwen2.5:14b", costPerCall: 0, latency: 2400 },
  { provider: "openai", model: "gpt-5-mini", costPerCall: 0.0028, latency: 720 },
];

export const mockApiCalls: ApiCostCall[] = Array.from({ length: 20 }, (_, i) => {
  const p = apiProviders[i % apiProviders.length];
  const tokensIn = 800 + Math.floor(Math.random() * 4000);
  const tokensOut = 300 + Math.floor(Math.random() * 1500);
  return {
    id: i + 1,
    provider: p.provider,
    model: p.model,
    endpoint: apiEndpoints[i % apiEndpoints.length],
    latency_ms: Math.floor(p.latency * (0.7 + Math.random() * 0.7)),
    tokens_in: tokensIn,
    tokens_out: tokensOut,
    cost_eur: p.costPerCall * (0.7 + Math.random() * 0.9),
    created_at: iso(new Date(now.getTime() - i * 1000 * 60 * 12)),
    ok: Math.random() > 0.08,
  };
});

export const mockApiCosts: ApiCosts = {
  total_today_eur: 0.42,
  total_month_eur: 7.31,
  by_provider: [
    {
      provider: "anthropic",
      calls_today: 14,
      calls_month: 285,
      cost_today_eur: 0.31,
      cost_month_eur: 5.18,
      avg_latency_ms: 1240,
    },
    {
      provider: "gemini",
      calls_today: 8,
      calls_month: 124,
      cost_today_eur: 0.07,
      cost_month_eur: 1.62,
      avg_latency_ms: 980,
    },
    {
      provider: "ollama",
      calls_today: 22,
      calls_month: 410,
      cost_today_eur: 0,
      cost_month_eur: 0,
      avg_latency_ms: 2200,
    },
    {
      provider: "openai",
      calls_today: 3,
      calls_month: 58,
      cost_today_eur: 0.04,
      cost_month_eur: 0.51,
      avg_latency_ms: 690,
    },
  ],
  recent_calls: mockApiCalls,
};

export const mockApiCostsPerDay = Array.from({ length: 30 }, (_, i) => {
  const d = daysAgo(29 - i);
  return {
    d: d.toLocaleDateString("es-ES", { day: "2-digit", month: "short" }),
    v: +(Math.random() * 0.6 + 0.05).toFixed(2),
  };
});

export const mock = {
  jobs: mockJobs,
  persons: mockPersons,
  posts: mockPosts,
  metrics: mockMetrics,
  companies: mockCompanies,
  comments: mockComments,
  jobsPerDay: mockJobsPerDay,
  appsBySource: mockAppsBySource,
  apiCosts: mockApiCosts,
  apiCostsPerDay: mockApiCostsPerDay,
};
