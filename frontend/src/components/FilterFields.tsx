export interface FilterValues {
  q: string;
  jobFamily: string;
  seniority: string;
  employmentType: string;
  remoteType: string;
  metroArea: string;
  jobBoard: string;
  classification: string;
  clearanceRequired: string;
  applicantMax: string;
  salaryMin: string;
  salaryMax: string;
  activeHiringMin: string;
  sortBy: string;
  sortDir: "asc" | "desc";
}

export type FilterKey = keyof FilterValues;

export const DEFAULT_FILTER_VALUES: FilterValues = {
  q: "",
  jobFamily: "",
  seniority: "",
  employmentType: "",
  remoteType: "",
  metroArea: "",
  jobBoard: "",
  classification: "",
  clearanceRequired: "",
  applicantMax: "",
  salaryMin: "",
  salaryMax: "",
  activeHiringMin: "",
  sortBy: "active_hiring_confidence",
  sortDir: "desc",
};

interface FieldsProps {
  values: FilterValues;
  onChange: <K extends FilterKey>(key: K, value: FilterValues[K]) => void;
}

const inputClass =
  "w-full rounded-lg border border-line bg-page px-3 py-2 text-ink-primary placeholder:text-ink-faint";

export function PrimaryFilterFields({ values, onChange }: FieldsProps) {
  return (
    <>
      <input
        aria-label="Search jobs"
        value={values.q}
        onChange={(event) => onChange("q", event.target.value)}
        placeholder="Search title, company, city, or state"
        className={inputClass}
      />

      <select
        aria-label="Role type"
        value={values.jobFamily}
        onChange={(event) => onChange("jobFamily", event.target.value)}
        className={inputClass}
      >
        <option value="">All role types</option>
        <option value="data analyst">Data analyst</option>
        <option value="data scientist">Data scientist</option>
        <option value="data engineer">Data engineer</option>
        <option value="software engineer">Software engineer</option>
        <option value="machine learning engineer">Machine learning engineer</option>
        <option value="business analyst">Business analyst</option>
        <option value="product manager">Product manager</option>
        <option value="technical program manager">Technical program manager</option>
        <option value="project manager">Project manager</option>
      </select>

      <input
        aria-label="Location"
        value={values.metroArea}
        onChange={(event) => onChange("metroArea", event.target.value)}
        placeholder="City, state, or metro area"
        className={inputClass}
      />

      <select
        aria-label="Seniority"
        value={values.seniority}
        onChange={(event) => onChange("seniority", event.target.value)}
        className={inputClass}
      >
        <option value="">All seniority</option>
        <option value="Entry">Entry</option>
        <option value="Mid">Mid</option>
        <option value="Senior">Senior</option>
        <option value="Lead">Lead</option>
        <option value="Executive">Executive</option>
      </select>

      <select
        aria-label="Employment type"
        value={values.employmentType}
        onChange={(event) => onChange("employmentType", event.target.value)}
        className={inputClass}
      >
        <option value="">All employment types</option>
        <option value="Full-time">Full-time</option>
        <option value="Part-time">Part-time</option>
        <option value="Contract">Contract</option>
        <option value="Internship">Internship</option>
      </select>

      <select
        aria-label="Work arrangement"
        value={values.remoteType}
        onChange={(event) => onChange("remoteType", event.target.value)}
        className={inputClass}
      >
        <option value="">All work types</option>
        <option value="Remote">Remote</option>
        <option value="Hybrid">Hybrid</option>
        <option value="Onsite">Onsite</option>
      </select>

      <select
        aria-label="Sort jobs by"
        value={values.sortBy}
        onChange={(event) => onChange("sortBy", event.target.value)}
        className={inputClass}
      >
        <option value="active_hiring_confidence">Sort by confidence</option>
        <option value="date_posted">Sort by posting date</option>
        <option value="date_first_seen">Sort by newest seen</option>
        <option value="ghost_job_probability">Sort by ghost probability</option>
        <option value="salary_max">Sort by salary</option>
        <option value="applicant_count">Sort by applicants</option>
      </select>

      <select
        aria-label="Sort direction"
        value={values.sortDir}
        onChange={(event) => onChange("sortDir", event.target.value as "asc" | "desc")}
        className={inputClass}
      >
        <option value="desc">High/new first</option>
        <option value="asc">Low/old first</option>
      </select>
    </>
  );
}

export function AdvancedFilterFields({ values, onChange }: FieldsProps) {
  return (
    <>
      <select
        aria-label="Job board"
        value={values.jobBoard}
        onChange={(event) => onChange("jobBoard", event.target.value)}
        className={inputClass}
      >
        <option value="">All job boards</option>
        <option value="company_site">Company site</option>
        <option value="linkedin">LinkedIn</option>
        <option value="indeed">Indeed</option>
        <option value="glassdoor">Glassdoor</option>
        <option value="ziprecruiter">ZipRecruiter</option>
        <option value="dice">Dice</option>
        <option value="monster">Monster</option>
        <option value="jobright">Jobright</option>
        <option value="simplify">Simplify</option>
      </select>

      <select
        aria-label="Listing classification"
        value={values.classification}
        onChange={(event) => onChange("classification", event.target.value)}
        className={inputClass}
      >
        <option value="">All listing types</option>
        <option value="original">Original</option>
        <option value="parallel">Parallel</option>
        <option value="repost">Repost</option>
      </select>

      <select
        aria-label="Security clearance"
        title="Detected from the listing title text. This is a best-effort match and may not catch every clearance phrasing."
        value={values.clearanceRequired}
        onChange={(event) => onChange("clearanceRequired", event.target.value)}
        className={inputClass}
      >
        <option value="">Any clearance status</option>
        <option value="true">Clearance mentioned</option>
        <option value="false">No clearance mentioned</option>
      </select>

      <div>
        <input
          aria-label="Max reported applicants"
          value={values.applicantMax}
          onChange={(event) => onChange("applicantMax", event.target.value)}
          placeholder="Max reported applicants"
          type="number"
          min="0"
          className={inputClass}
        />
        {values.applicantMax && (
          <p role="note" className="mt-1.5 text-xs leading-5 text-warning">
            Jobs with unavailable applicant count data are included in these results.
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <input
          aria-label="Minimum compensation"
          value={values.salaryMin}
          onChange={(event) => onChange("salaryMin", event.target.value)}
          placeholder="Min salary"
          type="number"
          min="0"
          className={inputClass}
        />
        <input
          aria-label="Maximum compensation"
          value={values.salaryMax}
          onChange={(event) => onChange("salaryMax", event.target.value)}
          placeholder="Max salary"
          type="number"
          min="0"
          className={inputClass}
        />
      </div>

      <div>
        <input
          aria-label="Minimum active hiring confidence"
          value={values.activeHiringMin}
          onChange={(event) => onChange("activeHiringMin", event.target.value)}
          placeholder="Minimum hiring confidence (0-100)"
          type="number"
          min="0"
          max="100"
          className={inputClass}
        />
        <p className="mt-1.5 text-xs leading-5 text-ink-faint">
          Hides jobs that have not been scored yet.
        </p>
      </div>
    </>
  );
}
