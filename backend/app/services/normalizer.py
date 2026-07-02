"""
Normalization and identity service.

The title pipeline is intentionally hybrid:
  * deterministic rules extract seniority and known technology specializations;
  * a controlled taxonomy maps title variants to a stable job family;
  * semantic similarity remains available in repost_detector.py as a fallback.

The module keeps normalize_title() and the original build_job_identity_key()
calling style backward compatible so existing scrapers continue to work.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Iterable, Optional, Tuple

from geopy.distance import geodesic
from geopy.geocoders import Nominatim

from app.core.config import settings


# ---------------------------------------------------------------------------
# Generic text helpers
# ---------------------------------------------------------------------------


def _clean_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = value.lower().strip()
    value = re.sub(r"[\u2010-\u2015]", "-", value)
    value = re.sub(r"[^a-z0-9+#./\-\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _slug(value: Optional[str]) -> str:
    value = _clean_text(value or "")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "unknown"


def normalize_company_name(name: str) -> str:
    """Normalize a company name without treating it as a job title."""
    cleaned = _clean_text(name)
    cleaned = re.sub(
        r"\b(incorporated|inc|llc|ltd|limited|corp|corporation|company|co)\.?$",
        "",
        cleaned,
    )
    return re.sub(r"\s+", " ", cleaned).strip()


# ---------------------------------------------------------------------------
# Technology title decomposition
# ---------------------------------------------------------------------------

# Ordered from most specific to least specific. The first match wins.
TECH_JOB_FAMILY_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("machine learning engineer", (
        r"\bmachine learning engineer\b", r"\bmachine learning\b.*\bengineer\b",
        r"\bml engineer\b", r"\bml\b.*\bengineer\b",
        r"\bai engineer\b", r"\bai\b.*\bengineer\b", r"\bdeep learning engineer\b",
    )),
    ("data scientist", (r"\bdata scientist\b", r"\bapplied scientist\b")),
    ("analytics engineer", (r"\banalytics engineer\b",)),
    ("data engineer", (r"\bdata engineer\b", r"\betl engineer\b")),
    ("data analyst", (
        r"\bdata analyst\b", r"\bbusiness intelligence analyst\b",
        r"\bbi analyst\b", r"\breporting analyst\b", r"\bbusiness analyst\b",
    )),
    ("devops engineer", (
        r"\bdevops engineer\b", r"\bsite reliability engineer\b",
        r"\bsre\b", r"\breliability engineer\b",
    )),
    ("security engineer", (
        r"\bsecurity engineer\b", r"\bcybersecurity engineer\b",
        r"\binformation security engineer\b", r"\bapplication security engineer\b",
    )),
    ("cloud engineer", (r"\bcloud engineer\b", r"\bcloud infrastructure engineer\b")),
    ("qa engineer", (
        r"\bqa engineer\b", r"\bquality assurance engineer\b",
        r"\btest automation engineer\b", r"\bsoftware test engineer\b",
    )),
    ("software engineer", (
        r"\bsoftware engineer\b", r"\bsoftware developer\b", r"\bswe\b",
        r"\bsde\b", r"\bfrontend engineer\b", r"\bfront end engineer\b",
        r"\bbackend engineer\b", r"\bback end engineer\b",
        r"\bfull[ -]?stack engineer\b", r"\bmobile engineer\b",
        r"\bios engineer\b", r"\bandroid engineer\b", r"\bprogrammer\b",
    )),
    ("database administrator", (
        r"\bdatabase administrator\b", r"\bdba\b", r"\bdatabase engineer\b",
    )),
    ("systems administrator", (
        r"\bsystems? administrator\b", r"\bsysadmin\b", r"\bit administrator\b",
    )),
    ("network engineer", (r"\bnetwork engineer\b", r"\bnetwork administrator\b")),
    ("solutions architect", (
        r"\bsolutions? architect\b", r"\bcloud architect\b", r"\btechnical architect\b",
    )),
    ("data architect", (r"\bdata architect\b",)),
    ("product manager", (
        r"\bproduct manager\b", r"\btechnical product manager\b", r"\bproduct owner\b",
    )),
    ("technical program manager", (
        r"\btechnical program manager\b", r"\btpm\b", r"\bengineering program manager\b",
    )),
    ("product designer", (
        r"\bproduct designer\b", r"\bux designer\b", r"\bui designer\b",
        r"\buser experience designer\b",
    )),
    ("it support specialist", (
        r"\bit support\b", r"\bhelp desk\b", r"\bdesktop support\b",
        r"\btechnical support specialist\b",
    )),
    ("quantitative analyst", (
        r"\bquantitative analyst\b", r"\bquantitative researcher\b", r"\bquant\b",
    )),
]

# Canonical specialization -> patterns. Multiple specializations may be retained.
SPECIALIZATION_PATTERNS: dict[str, tuple[str, ...]] = {
    "frontend": (r"\bfront[ -]?end\b", r"\breact\b", r"\bweb ui\b"),
    "backend": (r"\bback[ -]?end\b", r"\bserver side\b", r"\bapi platform\b"),
    "full_stack": (r"\bfull[ -]?stack\b",),
    "platform": (r"\bplatform\b",),
    "infrastructure": (r"\binfrastructure\b", r"\binfra\b"),
    "site_reliability": (r"\bsite reliability\b", r"\bsre\b"),
    "devops": (r"\bdevops\b", r"\bci/cd\b", r"\bdeveloper productivity\b"),
    "cloud": (r"\bcloud\b", r"\baws\b", r"\bazure\b", r"\bgcp\b"),
    "security": (r"\bsecurity\b", r"\bcyber\b", r"\bappsec\b"),
    "machine_learning": (r"\bmachine learning\b", r"\bml\b"),
    "artificial_intelligence": (r"\bartificial intelligence\b", r"\bgenerative ai\b", r"\bgenai\b"),
    "nlp": (r"\bnlp\b", r"\bnatural language processing\b"),
    "computer_vision": (r"\bcomputer vision\b", r"\bvision\b"),
    "data_platform": (r"\bdata platform\b", r"\bdata infrastructure\b"),
    "analytics": (r"\banalytics\b", r"\bbusiness intelligence\b", r"\bbi\b"),
    "database": (r"\bdatabase\b", r"\bpostgres\b", r"\bsql server\b"),
    "mobile": (r"\bmobile\b",),
    "ios": (r"\bios\b", r"\bswift\b"),
    "android": (r"\bandroid\b", r"\bkotlin\b"),
    "embedded": (r"\bembedded\b", r"\bfirmware\b", r"\breal[ -]?time\b"),
    "robotics": (r"\brobotics?\b", r"\bautonomous systems?\b"),
    "distributed_systems": (r"\bdistributed systems?\b", r"\bhigh scale\b"),
    "admin": (r"\badmin(?:istration)?\b", r"\badministrator\b"),
    "tech_lead": (r"\btechnical lead\b", r"\btech lead\b"),
    "payments": (r"\bpayments?\b", r"\bbilling\b"),
    "fraud": (r"\bfraud\b", r"\brisk platform\b"),
    "growth": (r"\bgrowth\b", r"\bacquisition\b"),
    "developer_experience": (r"\bdeveloper experience\b", r"\bdevex\b"),
}

SENIORITY_PATTERNS: dict[str, tuple[str, ...]] = {
    "executive": (
        r"\bchief\b", r"\bcto\b", r"\bcpo\b", r"\bcio\b", r"\bvp\b",
        r"\bvice president\b", r"\bhead of\b", r"\bdirector\b",
    ),
    "lead": (
        r"\bprincipal\b", r"\bstaff\b", r"\bdistinguished\b", r"\blead\b",
        r"\blevel 4\b", r"\biv\b",
    ),
    "senior": (
        r"\bsenior\b", r"\bsr\.?\b", r"\blevel 3\b", r"\biii\b",
    ),
    "entry": (
        r"\bintern(?:ship)?\b", r"\bjunior\b", r"\bjr\.?\b", r"\bnew grad\b",
        r"\bentry[ -]?level\b", r"\blevel 1\b",
    ),
    "mid": (
        r"\bmid[ -]?level\b", r"\bintermediate\b", r"\blevel 2\b", r"\bii\b",
    ),
}

# Compatibility alias retained for external imports/documentation.
TITLE_ALIASES = {
    "swe": "software engineer",
    "sde": "software engineer",
    "software developer": "software engineer",
    "business intelligence analyst": "data analyst",
    "bi analyst": "data analyst",
    "business analyst": "data analyst",
    "ml engineer": "machine learning engineer",
    "ai engineer": "machine learning engineer",
    "site reliability engineer": "devops engineer",
    "sre": "devops engineer",
}


def _matches_any(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def extract_seniority(raw_title: str) -> str:
    """
    Extract a stable seniority bucket.

    If a title explicitly contains "senior" and ends with "- lead", senior is
    retained as seniority while lead is treated as a specialization. If lead is
    the only level marker ("Lead Software Engineer"), the seniority is lead.
    """
    title = _clean_text(raw_title)

    if _matches_any(title, SENIORITY_PATTERNS["executive"]):
        return "executive"

    has_senior = _matches_any(title, SENIORITY_PATTERNS["senior"])
    has_entry = _matches_any(title, SENIORITY_PATTERNS["entry"])
    has_lead = _matches_any(title, SENIORITY_PATTERNS["lead"])

    if has_entry:
        return "entry"
    if has_senior:
        return "senior"
    if has_lead:
        return "lead"
    if _matches_any(title, SENIORITY_PATTERNS["mid"]):
        return "mid"
    return "mid"


def _extract_job_family(cleaned_title: str) -> tuple[str, float]:
    for family, patterns in TECH_JOB_FAMILY_PATTERNS:
        if _matches_any(cleaned_title, patterns):
            return family, 0.95

    # Graceful fallback for an unknown or non-tech title. This keeps ingestion
    # working without pretending the taxonomy recognized the role.
    fallback = cleaned_title
    for patterns in SENIORITY_PATTERNS.values():
        for pattern in patterns:
            fallback = re.sub(pattern, " ", fallback, flags=re.IGNORECASE)
    fallback = re.sub(r"\b(level|grade)\s*[0-9ivx]+\b", " ", fallback)
    fallback = re.sub(r"\s+", " ", fallback).strip(" -/")
    return fallback or "unknown role", 0.45


def _extract_specializations(cleaned_title: str, seniority: str) -> list[str]:
    found: set[str] = set()
    for specialization, patterns in SPECIALIZATION_PATTERNS.items():
        if _matches_any(cleaned_title, patterns):
            found.add(specialization)

    # "Lead" is a specialization only when another explicit level marker is
    # present or it appears after a delimiter. Otherwise it is seniority.
    lead_as_suffix = bool(re.search(r"(?:-|/|\(|,)\s*(?:technical\s+|tech\s+)?lead\b", cleaned_title))
    if seniority != "lead" and (lead_as_suffix or "lead" in cleaned_title):
        found.add("tech_lead")

    # Avoid redundant tags for families whose meaning already supplies them.
    redundant_by_family = {
        "machine learning engineer": {"machine_learning"},
        "data analyst": {"analytics"},
        "analytics engineer": {"analytics"},
        "security engineer": {"security"},
        "cloud engineer": {"cloud"},
        "devops engineer": {"devops"},
        "database administrator": {"database", "admin"},
        "systems administrator": {"admin"},
    }
    family, _ = _extract_job_family(cleaned_title)
    found -= redundant_by_family.get(family, set())
    return sorted(found)


def decompose_title(raw_title: str) -> dict:
    """
    Convert a raw title into structured fields used by identity resolution.

    Returns:
        {
          "core_title": "software engineer",
          "job_family": "software engineer",
          "specialization": "admin",          # comma-separated convenience field
          "specializations": ["admin"],
          "seniority": "senior",
          "title_normalized": "software engineer",
          "parse_confidence": 0.95,
          "is_tech_role": True,
        }
    """
    cleaned = _clean_text(raw_title)
    seniority = extract_seniority(cleaned)
    job_family, confidence = _extract_job_family(cleaned)
    specializations = _extract_specializations(cleaned, seniority)

    is_tech_role = any(job_family == family for family, _ in TECH_JOB_FAMILY_PATTERNS)
    return {
        "core_title": job_family,
        "job_family": job_family,
        "specialization": ",".join(specializations) or None,
        "specializations": specializations,
        "seniority": seniority,
        "title_normalized": job_family,
        "parse_confidence": confidence,
        "is_tech_role": is_tech_role,
    }


def normalize_title(raw_title: str) -> str:
    """Backward-compatible wrapper returning the canonical job family."""
    return decompose_title(raw_title)["title_normalized"]


# ---------------------------------------------------------------------------
# Location normalization
# ---------------------------------------------------------------------------

LOCATION_ABBREVIATIONS = {
    "la": "Los Angeles", "l.a.": "Los Angeles", "los angeles": "Los Angeles",
    "greater la": "Los Angeles", "la metro": "Los Angeles",
    "sf": "San Francisco", "san fran": "San Francisco",
    "san francisco": "San Francisco", "bay area": "San Francisco", "sfba": "San Francisco",
    "nyc": "New York", "new york city": "New York", "ny": "New York",
    "new york": "New York", "greater new york": "New York",
    "dc": "Washington", "washington dc": "Washington", "wash dc": "Washington",
    "chi": "Chicago", "chicago": "Chicago", "atl": "Atlanta", "atlanta": "Atlanta",
    "sea": "Seattle", "seattle": "Seattle", "bos": "Boston", "boston": "Boston",
    "austin": "Austin", "atx": "Austin", "dallas": "Dallas", "dfw": "Dallas",
    "houston": "Houston", "hou": "Houston", "miami": "Miami", "mia": "Miami",
    "denver": "Denver", "den": "Denver", "phoenix": "Phoenix", "phx": "Phoenix",
    "san diego": "San Diego", "sd": "San Diego",
    "ca": "California", "tx": "Texas", "wa": "Washington", "fl": "Florida",
    "il": "Illinois", "ma": "Massachusetts", "co": "Colorado", "az": "Arizona",
    "ga": "Georgia",
}

_geocoder = None


def _get_geocoder():
    global _geocoder
    if _geocoder is None:
        _geocoder = Nominatim(user_agent="joblens-normalizer")
    return _geocoder


def normalize_location_text(raw: str) -> str:
    cleaned = _clean_text(raw)
    return LOCATION_ABBREVIATIONS.get(cleaned, (raw or "").strip())


def geocode_location(location_str: str) -> Optional[Tuple[float, float, str]]:
    try:
        geo = _get_geocoder()
        normalized = normalize_location_text(location_str)
        result = geo.geocode(normalized, addressdetails=True, language="en", timeout=5)
        if not result:
            return None
        address = result.raw.get("address", {})
        city = address.get("city") or address.get("town") or address.get("village", "")
        state = address.get("state", "")
        metro = f"{city}, {state}".strip(", ") if city else state
        return result.latitude, result.longitude, metro
    except Exception:
        return None


def locations_in_same_cluster(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    radius_miles: Optional[float] = None,
) -> bool:
    radius = radius_miles or settings.location_cluster_radius_miles
    return geodesic((lat1, lon1), (lat2, lon2)).miles <= radius


def is_remote(remote_type: Optional[str]) -> bool:
    return (remote_type or "").strip().lower() == "remote"


def location_bucket(metro_area: Optional[str], remote_type: Optional[str]) -> str:
    """Remote roles ignore advertised region; onsite/hybrid roles retain metro."""
    if is_remote(remote_type):
        return "remote"
    if not metro_area:
        return "unknown_location"
    return _slug(metro_area.split(",")[0])


# ---------------------------------------------------------------------------
# Skill extraction
# ---------------------------------------------------------------------------

SKILL_ALIASES = {
    "python": "Python", "py": "Python", "sql": "SQL",
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "mysql": "MySQL",
    "r ": "R", "r,": "R", "tableau": "Tableau", "power bi": "Power BI",
    "powerbi": "Power BI", "excel": "Excel", "spark": "Apache Spark",
    "pyspark": "Apache Spark", "airflow": "Apache Airflow", "dbt": "dbt",
    "aws": "AWS", "azure": "Azure", "gcp": "GCP", "google cloud": "GCP",
    "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "pytorch": "PyTorch", "tensorflow": "TensorFlow", "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn", "pandas": "pandas", "numpy": "NumPy",
    "react": "React", "typescript": "TypeScript", "javascript": "JavaScript",
    "js": "JavaScript", "fastapi": "FastAPI", "django": "Django", "flask": "Flask",
    "java": "Java", "scala": "Scala", "go ": "Go", "golang": "Go", "rust": "Rust",
    "snowflake": "Snowflake", "databricks": "Databricks", "redshift": "Redshift",
    "bigquery": "BigQuery", "looker": "Looker", "sas": "SAS", "spss": "SPSS",
    "mlflow": "MLflow", "git": "Git", "linux": "Linux", "bash": "Bash", "shell": "Bash",
}

SKILL_CATEGORIES = {
    "Python": "Language", "SQL": "Language", "R": "Language", "Java": "Language",
    "Scala": "Language", "Go": "Language", "Rust": "Language",
    "JavaScript": "Language", "TypeScript": "Language",
    "Tableau": "Visualization", "Power BI": "Visualization", "Looker": "Visualization",
    "Excel": "Productivity", "AWS": "Cloud", "Azure": "Cloud", "GCP": "Cloud",
    "Docker": "DevOps", "Kubernetes": "DevOps", "PostgreSQL": "Database",
    "MySQL": "Database", "Snowflake": "Database", "BigQuery": "Database",
    "Redshift": "Database", "Databricks": "Data Platform", "Apache Spark": "Data Platform",
    "Apache Airflow": "Data Platform", "dbt": "Data Platform", "PyTorch": "ML",
    "TensorFlow": "ML", "scikit-learn": "ML", "MLflow": "ML",
    "pandas": "Library", "NumPy": "Library", "FastAPI": "Framework",
    "Django": "Framework", "Flask": "Framework", "React": "Framework",
    "SAS": "Analytics", "SPSS": "Analytics", "Git": "Tools", "Linux": "Tools", "Bash": "Tools",
}


def extract_skills(description: str) -> list[dict]:
    if not description:
        return []
    desc_lower = description.lower()
    found: dict[str, dict] = {}
    for alias, normalized in SKILL_ALIASES.items():
        if alias in desc_lower and normalized not in found:
            found[normalized] = {
                "skill": normalized,
                "skill_normalized": normalized.lower(),
                "skill_category": SKILL_CATEGORIES.get(normalized),
            }
    return list(found.values())


# ---------------------------------------------------------------------------
# Job identity
# ---------------------------------------------------------------------------


def _normalize_specializations(value: Optional[Iterable[str] | str]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = re.split(r"[,|]", value)
    else:
        values = list(value)
    return sorted({_slug(item) for item in values if item})


def build_identity_fingerprint(
    company_name: str,
    job_family: str,
    specializations: Optional[Iterable[str] | str] = None,
    seniority: Optional[str] = None,
    remote_type: Optional[str] = None,
    employment_type: Optional[str] = None,
) -> str:
    """
    Location-independent SHA-256 identity used to find related listings.

    It deliberately ignores advertised metro so remote/multi-location listings
    can be compared, while location compatibility is decided later by the
    repost classifier.
    """
    specs = "+".join(_normalize_specializations(specializations)) or "general"
    material = "|".join([
        _slug(normalize_company_name(company_name)),
        _slug(job_family),
        specs,
        _slug(seniority or "mid"),
        _slug(remote_type or "unknown"),
        _slug(employment_type or "full_time"),
    ])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_job_identity_key(
    company_name: str,
    title_normalized: Optional[str] = None,
    metro_area: Optional[str] = None,
    *,
    job_family: Optional[str] = None,
    specializations: Optional[Iterable[str] | str] = None,
    seniority: Optional[str] = None,
    remote_type: Optional[str] = None,
    employment_type: Optional[str] = None,
) -> str:
    """
    Human-readable identity key.

    The first three positional arguments preserve the old scraper API. New
    callers should provide the structured keyword arguments. Remote listings
    intentionally use one location bucket regardless of advertised region.
    """
    family = job_family or title_normalized or "unknown role"
    specs = "+".join(_normalize_specializations(specializations)) or "general"
    parts = [
        _slug(normalize_company_name(company_name)),
        _slug(family),
        specs,
        _slug(seniority or "mid"),
        _slug(employment_type or "full_time"),
        location_bucket(metro_area, remote_type),
    ]
    return "__".join(parts)


def enrich_job_identity(job_dict: dict) -> dict:
    """Add/recompute all structured identity fields on a scraper result."""
    title_parts = decompose_title(job_dict.get("title_raw", ""))
    job_dict.update({
        "title_normalized": title_parts["title_normalized"],
        "job_family": title_parts["job_family"],
        "specialization": title_parts["specialization"],
        "specializations": title_parts["specializations"],
        "seniority": title_parts["seniority"],
        "title_parse_confidence": title_parts["parse_confidence"],
    })
    job_dict["job_identity_key"] = build_job_identity_key(
        job_dict.get("company_name", ""),
        job_family=title_parts["job_family"],
        specializations=title_parts["specializations"],
        seniority=title_parts["seniority"],
        metro_area=job_dict.get("metro_area"),
        remote_type=job_dict.get("remote_type"),
        employment_type=job_dict.get("employment_type"),
    )
    job_dict["identity_fingerprint"] = build_identity_fingerprint(
        job_dict.get("company_name", ""),
        title_parts["job_family"],
        title_parts["specializations"],
        title_parts["seniority"],
        job_dict.get("remote_type"),
        job_dict.get("employment_type"),
    )
    return job_dict


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

_model = None


def embed_text(text: str) -> list:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(settings.embedding_model)
    return _model.encode(text, normalize_embeddings=True).tolist()
