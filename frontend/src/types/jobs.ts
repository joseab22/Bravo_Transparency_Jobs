// =============================================================================
// JobLens — TypeScript types matching backend Pydantic schemas
// =============================================================================

export type JobSource =
  | "linkedin" | "indeed" | "glassdoor" | "ziprecruiter"
  | "dice" | "monster" | "simplify" | "jobright" | "company_site";

export type RemoteType = "Remote" | "Hybrid" | "Onsite";
export type SeniorityLevel = "Entry" | "Mid" | "Senior" | "Lead" | "Executive";
export type EmploymentType = "Full-time" | "Part-time" | "Contract" | "Internship";

export const SOURCE_LABELS: Record<JobSource, string> = {
  linkedin: "LinkedIn", indeed: "Indeed", glassdoor: "Glassdoor",
  ziprecruiter: "ZipRecruiter", dice: "Dice", monster: "Monster",
  simplify: "Simplify", jobright: "Jobright", company_site: "Company Site",
};

export const SOURCE_COLORS: Record<JobSource, string> = {
  linkedin: "#0A66C2", indeed: "#003A9B", glassdoor: "#0CAA41",
  ziprecruiter: "#FF6900", dice: "#E8262A", monster: "#6E3EBB",
  simplify: "#111827", jobright: "#1A73E8", company_site: "#6B7280",
};

export interface Company {
  id: number;
  name: string;
  industry: string | null;
  glassdoor_rating: number | null;
  ghost_job_rate: number | null;
  avg_reposts: number | null;
  median_time_to_fill: number | null;
  hiring_intensity: number | null;
}

export interface Skill {
  skill: string;
  skill_category: string | null;
}

export interface SourceSighting {
  source: JobSource;
  source_url: string | null;
  applicant_count: number | null;
  first_seen: string;
  last_seen: string;
}

export interface RepostEvent {
  occurrence_number: number;
  date_seen: string;
  source: JobSource | null;
  days_since_previous: number | null;
}

export interface JobEvent {
  id: number;
  event_type: string;
  timestamp: string;
  source: JobSource | null;
  description: string | null;
  payload: Record<string, unknown> | null;
}

export interface JobListItem {
  id: number;
  title_normalized: string;
  title_raw: string;
  company: Company;
  location_raw: string | null;
  city: string | null;
  state: string | null;
  metro_area: string | null;
  remote_type: RemoteType | null;
  seniority: SeniorityLevel | null;
  employment_type: EmploymentType | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_listed: boolean;
  date_posted: string | null;
  date_first_seen: string;
  days_active: number;
  applicant_count: number | null;
  repost_count: number;
  is_active: boolean;
  // Transparency scores
  ghost_job_probability: number | null;
  ghost_confidence: number | null;
  health_score: number | null;
  competition_score: number | null;
  interview_opportunity_score: number | null;
  salary_fairness_score: number | null;
  // Analytics
  activity_score: number | null;
  description_change_score: number | null;
  applicant_trend: number | null;
  salary_trend: number | null;
  // Relations
  source_sightings: SourceSighting[];
  skills: Skill[];
}

export interface JobDetail extends JobListItem {
  description_raw: string | null;
  education_required: string | null;
  experience_years_min: number | null;
  experience_years_max: number | null;
  market_salary: number | null;
  stability_score: number | null;
  department: string | null;
  source_url: string | null;
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

export interface MarketStats {
  total_active_jobs: number;
  avg_ghost_probability: number;
  avg_health_score: number;
  high_ghost_risk_count: number;
  top_industries: { industry: string; count: number }[];
  top_skills: { skill: string; count: number }[];
  avg_days_active: number;
  total_applicants: number;
}

export interface JobFilters {
  q?: string;
  industry?: string;
  remote_type?: RemoteType;
  seniority?: SeniorityLevel;
  employment_type?: EmploymentType;
  metro_area?: string;
  salary_min?: number;
  salary_max?: number;
  ghost_max?: number;
  health_min?: number;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
  page?: number;
  page_size?: number;
}
