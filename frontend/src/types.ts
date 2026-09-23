// Mirror of backend/app/schemas.py - THE CONTRACT. Change both in the same commit.

export type UpdateType = "as_publication" | "entry_into_force" | "consultation" | "simulated";
export type Urgency = "high" | "medium" | "low";
export type DraftStatus = "pending" | "approved" | "rejected" | "revision_requested";
export type Language = "DE" | "FR" | "EN" | "IT";

export interface DepartmentIn {
  name: string;
  contact_email: string;
  functions: string[];
  responsibilities: string;
}
export interface Department extends DepartmentIn {
  id: number;
}

export interface CompanyIn {
  name: string;
  industry: string;
  description: string;
  size_band: string;
  hq_canton: string;
  jurisdictions: string[];
  flags: Record<string, boolean>;
  legal_context: string;
  key_challenges: string;
  topics: string[];
  preferred_language: Language;
  departments: DepartmentIn[];
}
export interface Company extends Omit<CompanyIn, "departments"> {
  id: number;
  departments: Department[];
  created_at: string;
  updated_at: string;
}

export interface SourceRef {
  source: string;
  external_id: string;
  url: string | null;
  version: string | null;
  fetched_at: string;
  kind?: string;
}
export interface SourceArticle {
  ref: string;
  text: string;
}
export interface Classification {
  topics: string[];
  functional_teams: string[];
  triggered_flags: string[];
  affected_business_types: string[];
  applies_to?: string[]; // "all_legal_entities" | "employers"
  urgency: Urgency;
  rationale: string;
  model_version: string;
  prompt_version: string;
  classified_at: string;
}
export interface RegulatoryUpdateListItem {
  id: string;
  title: string;
  update_type: UpdateType;
  jurisdiction: string;
  eli_uri: string | null;
  publication_date: string | null;
  entry_into_force_date: string | null;
  consultation_deadline: string | null;
  source_language: string;
  is_simulated: boolean;
  sources: SourceRef[];
  classification: Classification | null;
}
export interface RegulatoryUpdate extends RegulatoryUpdateListItem {
  dedup_key: string;
  sr_number: string | null;
  source_text: string | null;
  source_articles: SourceArticle[];
  source_text_url: string | null;
  source_url: string | null;
  source_version: string | null;
  metadata_extra: Record<string, unknown>;
  fetched_at: string;
}

export interface RuleHit {
  rule: string;
  detail: string;
  weight: number;
}
export interface Match {
  id: number;
  update_id: string;
  company_id: number;
  matched: boolean;
  relevance_score: number;
  rule_hits: RuleHit[];
  llm_reason: string;
  model_version: string;
  prompt_version: string;
  created_at: string;
}

export interface Citation {
  claim: string;
  eli: string | null;
  article: string | null;
  quote?: string | null;
  source_url?: string | null;
}
export interface AffectedDepartment {
  department_id: number | null;
  name: string;
  why: string;
}
export interface NextStep {
  action: string;
  department?: string | null;
  due?: string | null;
}
export interface RevisionEntry {
  version: number;
  at: string;
  by: string;
  change: string;
  snapshot: Record<string, unknown>;
}
export interface ReviewerComment {
  at: string;
  by: string;
  decision: string;
  comment: string;
}
export interface Draft {
  id: number;
  match_id: number;
  company_id: number;
  update_id: string;
  version: number;
  summary: string;
  affected_departments: AffectedDepartment[];
  next_steps: NextStep[];
  urgency: Urgency;
  citations: Citation[];
  status: DraftStatus;
  reviewer_comments: ReviewerComment[];
  revision_history: RevisionEntry[];
  model_version: string;
  prompt_version: string;
  edited_by_lawyer: boolean;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
  warnings: string[];
}
export interface DraftDetail extends Draft {
  update: RegulatoryUpdate;
  match: Match;
  company: Company;
}
export type DraftEdit = Partial<Pick<Draft, "summary" | "affected_departments" | "next_steps" | "urgency" | "citations">>;

export interface Alert {
  id: number;
  draft_id: number;
  company_id: number;
  departments: AffectedDepartment[];
  delivered_at: string;
  reviewed_by: string;
  read_at: string | null;
  title: string;
  summary: string;
  next_steps: NextStep[];
  urgency: Urgency;
  citations: Citation[];
  source_url: string | null;
  is_simulated: boolean;
  disclaimer: string;
}
export interface EmailPreview {
  to: string[];
  subject: string;
  body_text: string;
}
export interface AuditLogEntry {
  id: number;
  timestamp: string;
  actor: string;
  action: string;
  object_type: string;
  object_id: string;
  details: Record<string, unknown>;
}
export interface PipelineResult {
  step: string;
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
  info: Record<string, unknown>;
}
export interface Meta {
  functional_teams: string[];
  activity_flags: Record<string, string>;
  size_bands: string[];
  cantons: string[];
  disclaimer: string;
  demo_mode: boolean;
  llm_provider: string;
  llm_model: string;
}
