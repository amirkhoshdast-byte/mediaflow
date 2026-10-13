export type Role =
  | "trend_analyst"
  | "media_monitor"
  | "ai_operator"
  | "content_lead"
  | "narrative_strategist"
  | "diplomatic_editor"
  | "president_office"
  | "sysadmin";
export type Risk = "low" | "medium" | "high" | "critical";
export type Stage = "draft" | "tone_review" | "approved" | "published";

export interface Me {
  id: string;
  username: string;
  display_name: string;
  role: Role;
  ui_language: string;
  permissions: string[];
}
export interface Signal {
  id: string;
  status: "analyzing" | "ready" | "failed";
  title: string | null;
  summary: string | null;
  category: string | null;
  region: string | null;
  risk: Risk | null;
  approach: string | null;
  opportunity: string | null;
  sentiment: number | null;
  zone: "green" | "yellow" | "red" | "rebuttal" | null;
  relevance: number | null;
  error: string | null;
  text: string;
  url: string | null;
  created_at: string;
}
export interface Checks {
  lengths: number[];
  too_long: boolean;
  near_limit: boolean;
  hashtags: number;
  too_many_hashtags: boolean;
  has_emoji: boolean;
}
export interface Draft {
  id: string;
  signal_id: string | null;
  topic: string | null;
  format: string;
  language: string;
  persona: string;
  pillar: string;
  angle: string | null;
  generation_group: string | null;
  parts: string[];
  stage: Stage;
  risk: Risk;
  checks: Checks;
  created_at: string;
  updated_at: string;
  published_at: string | null;
}
export interface Meta {
  categories: string[];
  personas: string[];
  pillars: string[];
  languages: string[];
  limits: { soft: number; hard: number };
  targets: { posts: number; replies: number };
}
export interface Stats {
  posts: { done: number; target: number };
  replies: { done: number; target: number };
  signals_today: number;
  stages: Record<Stage, number>;
}

export interface KbDoc {
  id: string;
  title: string;
  doc_type: string;
  sensitivity: "normal" | "sensitive";
  filename: string;
  status: "processing" | "ready" | "failed";
  error: string | null;
  chunks: number;
  created_at: string;
}
export interface KbHit {
  doc_id: string;
  title: string;
  doc_type: string;
  sensitivity: string;
  text: string;
  score: number;
}

export interface RedLine {
  id: string;
  kind: "topic" | "phrase";
  pattern: string;
  description: string | null;
  severity: Risk;
  active: boolean;
}

export interface IntelOverview {
  window_hours: number;
  total: number;
  analyzing: number;
  failed: number;
  hidden_low_relevance: number;
  by_zone: Record<string, number>;
  by_category: Record<string, number>;
  top: Signal[];
  high_risk: Signal[];
  rebuttals: Signal[];
  sources: { active: number; failing: number; last_fetch: string | null };
}
export interface Source {
  id: string;
  type: "rss" | "gdelt";
  name: string;
  url: string | null;
  query: string | null;
  language: string;
  domain: string | null;
  active: boolean;
  last_fetched_at: string | null;
  last_error: string | null;
}

export interface ToneIssue {
  source: "rule" | "model";
  type:
    "red_line_phrase" | "red_line_topic" | "office_language" | "format" | "tone" | "fact" | "other";
  quote: string | null;
  reason: string;
  severity: Risk | null;
  suggestion: string | null;
}
export interface ToneReview {
  id: string;
  status: "analyzing" | "ready" | "failed";
  score: number | null;
  issues: ToneIssue[];
  suggested_parts: string[] | null;
  error: string | null;
  stale: boolean;
}
