export interface Company {
  id: number;
  name: string;
  industry?: string | null;
  hiring_intensity?: number | null;
  ghost_job_rate?: number | null;
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
  days_active: number;
  applicant_count?: number | null;
  listing_classification: "original" | "parallel" | "repost" | string;
  repost_count: number;
  is_active: boolean;
  active_hiring_confidence?: number | null;
  ghost_job_probability?: number | null;
  health_score?: number | null;
  activity_score?: number | null;
  canonical_sources: CanonicalSource[];
  skills: Skill[];
}

export interface PaginatedJobs {
  total: number;
  page: number;
  page_size: number;
  pages: number;
  results: JobListItem[];
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
  collapse_canonical?: boolean;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}
