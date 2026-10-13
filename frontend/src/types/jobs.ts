export interface Company {
  id: number;
  name: string;
  industry?: string | null;
  hiring_intensity?: number | null;
  ghost_job_rate?: number | null;
  glassdoor_rating?: number | null;
  website?: string | null;
  logo_url?: string | null;
}

export interface Skill {
  skill: string;
  skill_category?: string | null;
}

export interface CanonicalSource {
  sighting_key: string;
  source: string;
  publisher_name: string;
  collection_provider?: string | null;
  source_url?: string | null;
  external_id?: string | null;
  is_direct: boolean;
  first_seen: string;
  last_seen: string;
  is_active: boolean;
  listing_ids: number[];
}

export interface ScoreComponent {
  key: string;
  label: string;
  points: number;
  maximum?: number | null;
  tone: "positive" | "neutral" | "negative";
  detail: string;
}

export interface ActiveHiringReasoning {
  score: number;
  label: string;
  summary: string;
  formula: string;
  components: ScoreComponent[];
  signals: string[];
  limitations: string[];
}

export interface JobListItem {
  id: number;
  source: string;
  publisher_name?: string | null;
  collection_provider?: string | null;
  source_url?: string | null;
  title_raw: string;
  title_normalized: string;
  job_family?: string | null;
  specialization?: string | null;
  company: Company;
  location_raw?: string | null;
  metro_area?: string | null;
  remote_type?: string | null;
  seniority?: string | null;
  employment_type?: string | null;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency: string;
  salary_listed: boolean;
  date_posted?: string | null;
  date_first_seen: string;
  date_last_seen: string;
  days_active: number;
  applicant_count?: number | null;
  listing_classification: "original" | "parallel" | "repost" | string;
  repost_count: number;
  is_active: boolean;
  active_hiring_confidence?: number | null;
  active_hiring_reasoning?: ActiveHiringReasoning | null;
  ghost_job_probability?: number | null;
  ghost_confidence?: number | null;
  health_score?: number | null;
  activity_score?: number | null;
  canonical_sources: CanonicalSource[];
  skills: Skill[];
  is_favorited: boolean;
  is_applied: boolean;
  note?: string | null;
}

export interface RepostEvent {
  occurrence_number: number;
  date_seen: string;
  source?: string | null;
  days_since_previous?: number | null;
}

export interface JobEvent {
  id: number;
  event_type: string;
  timestamp: string;
  source?: string | null;
  description?: string | null;
  payload?: Record<string, unknown> | null;
}

export interface JobDetail extends JobListItem {
  description_raw?: string | null;
  education_required?: string | null;
  experience_years_min?: number | null;
  experience_years_max?: number | null;
  market_salary?: number | null;
  stability_score?: number | null;
  department?: string | null;
  repost_events: RepostEvent[];
  events: JobEvent[];
}

export interface PaginatedJobs {
  total: number;
  page: number;
  page_size: number;
  pages: number;
  results: JobListItem[];
}

export type ApplicationStatus = "applied" | "interviewing" | "offer" | "rejected" | "withdrawn";

export interface FavoriteEntry {
  job_posting_id: number;
  created_at: string;
  job: JobListItem;
}

export interface ApplicationEntry {
  job_posting_id: number;
  status: ApplicationStatus;
  applied_date?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  job: JobListItem;
}

export interface ApplicationInput {
  status: ApplicationStatus;
  applied_date?: string | null;
  notes?: string | null;
}

export interface NoteEntry {
  job_posting_id: number;
  // note is the standalone note, editable from the Notes tab. application_note
  // mirrors JobApplication.notes for the same job when present -- it is
  // read-only here; it's only ever edited from the Applications tab.
  note?: string | null;
  application_note?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  job: JobListItem;
}

export interface RecentlyViewedEntry {
  job_posting_id: number;
  viewed_at: string;
  job: JobListItem;
}

export interface DismissalEntry {
  job_posting_id: number;
  created_at: string;
  job: JobListItem;
}

export interface SavedSearchEntry {
  id: number;
  name: string;
  filters: Record<string, unknown>;
  created_at: string;
}

export interface JobFilters {
  page?: number;
  page_size?: number;
  q?: string;
  job_family?: string;
  job_board?: string;
  classification?: string;
  remote_type?: string;
  seniority?: string;
  employment_type?: string;
  metro_area?: string;
  salary_min?: number;
  salary_max?: number;
  ghost_max?: number;
  health_min?: number;
  active_hiring_min?: number;
  applicant_max?: number;
  max_age_days?: number;
  clearance_required?: boolean;
  show_missing_description?: boolean;
  collapse_canonical?: boolean;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}

export interface MarketStats {
  total_active_jobs: number;
  scored_active_jobs: number;
  avg_active_hiring_confidence: number;
  avg_ghost_probability: number;
  avg_health_score: number;
  high_ghost_risk_count: number;
  classification_counts: { classification: string; count: number }[];
  top_industries: { industry: string; count: number }[];
  top_skills: { skill: string; count: number }[];
  avg_days_active: number;
  total_applicants: number;
}
