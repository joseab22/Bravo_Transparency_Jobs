"""
Normalization service.

Handles:
  - Job title normalization (rule-based → later classifier)
  - Location normalization (abbreviation dict + geocoding)
  - Skill extraction and normalization
  - Job identity key generation
"""

import re
import unicodedata
from typing import Optional, Tuple
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from app.core.config import settings


# ---------------------------------------------------------------------------
# Title normalization
# ---------------------------------------------------------------------------

TITLE_PREFIXES_TO_STRIP = [
    r"\b(junior|jr\.?|associate|assoc\.?|staff|principal|lead|chief|head of)\b",
    r"\b(sr\.?|senior)\b",
    r"\b(i+|iv|v)\b$",  # roman numerals at end
    r"\b[1-5]\b$",       # numeric levels at end
]

TITLE_ALIASES = {
    "software engineer": "software engineer",
    "swe": "software engineer",
    "sde": "software engineer",
    "software developer": "software engineer",
    "data analyst": "data analyst",
    "business analyst": "data analyst",
    "reporting analyst": "data analyst",
    "bi analyst": "data analyst",
    "business intelligence analyst": "data analyst",
    "analytics engineer": "analytics engineer",
    "data engineer": "data engineer",
    "de": "data engineer",
    "data scientist": "data scientist",
    "ml engineer": "machine learning engineer",
    "machine learning engineer": "machine learning engineer",
    "ai engineer": "machine learning engineer",
    "product manager": "product manager",
    "pm": "product manager",
    "program manager": "program manager",
    "project manager": "project manager",
    "data architect": "data architect",
    "solutions architect": "solutions architect",
    "devops engineer": "devops engineer",
    "site reliability engineer": "devops engineer",
    "sre": "devops engineer",
    "frontend engineer": "frontend engineer",
    "front end engineer": "frontend engineer",
    "backend engineer": "backend engineer",
    "back end engineer": "backend engineer",
    "full stack engineer": "fullstack engineer",
    "fullstack engineer": "fullstack engineer",
    "quantitative analyst": "quantitative analyst",
    "quant": "quantitative analyst",
}

SENIORITY_KEYWORDS = {
    "entry": ["junior", "jr", "associate", "entry", "i ", "level 1", "new grad", "intern"],
    "mid": ["mid", "ii ", "level 2", "level ii", "intermediate"],
    "senior": ["senior", "sr", "iii ", "level 3", "level iii", "experienced"],
    "lead": ["lead", "principal", "staff", "iv ", "level 4"],
    "executive": ["director", "vp", "head of", "chief", "cto", "cpo"],
}


def normalize_title(raw_title: str) -> str:
    title = raw_title.lower().strip()
    title = unicodedata.normalize("NFKD", title)
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()

    # Check aliases first
    for alias, normalized in TITLE_ALIASES.items():
        if alias in title:
            return normalized

    # Strip level/seniority markers
    for pattern in TITLE_PREFIXES_TO_STRIP:
        title = re.sub(pattern, "", title, flags=re.IGNORECASE).strip()

    return re.sub(r"\s+", " ", title).strip()


def extract_seniority(raw_title: str) -> Optional[str]:
    title_lower = raw_title.lower()
    for level, keywords in SENIORITY_KEYWORDS.items():
        if any(kw in title_lower for kw in keywords):
            return level
    return "mid"  # default


# ---------------------------------------------------------------------------
# Location normalization
# ---------------------------------------------------------------------------

LOCATION_ABBREVIATIONS = {
    # Cities
    "la": "Los Angeles",
    "l.a.": "Los Angeles",
    "los angeles": "Los Angeles",
    "greater la": "Los Angeles",
    "la metro": "Los Angeles",
    "sf": "San Francisco",
    "san fran": "San Francisco",
    "san francisco": "San Francisco",
    "bay area": "San Francisco",
    "sfba": "San Francisco",
    "nyc": "New York",
    "new york city": "New York",
    "ny": "New York",
    "new york": "New York",
    "greater new york": "New York",
    "dc": "Washington",
    "washington dc": "Washington",
    "wash dc": "Washington",
    "chi": "Chicago",
    "chicago": "Chicago",
    "atl": "Atlanta",
    "atlanta": "Atlanta",
    "sea": "Seattle",
    "seattle": "Seattle",
    "bos": "Boston",
    "boston": "Boston",
    "austin": "Austin",
    "atx": "Austin",
    "dallas": "Dallas",
    "dfw": "Dallas",
    "houston": "Houston",
    "hou": "Houston",
    "miami": "Miami",
    "mia": "Miami",
    "denver": "Denver",
    "den": "Denver",
    "phoenix": "Phoenix",
    "phx": "Phoenix",
    "san diego": "San Diego",
    "sd": "San Diego",
    # States
    "ca": "California",
    "tx": "Texas",
    "ny": "New York",
    "wa": "Washington",
    "fl": "Florida",
    "il": "Illinois",
    "ma": "Massachusetts",
    "co": "Colorado",
    "az": "Arizona",
    "ga": "Georgia",
}


_geocoder = None


def _get_geocoder():
    global _geocoder
    if _geocoder is None:
        _geocoder = Nominatim(user_agent="joblens-normalizer")
    return _geocoder


def normalize_location_text(raw: str) -> str:
    """Apply abbreviation dict to raw location string."""
    cleaned = raw.lower().strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return LOCATION_ABBREVIATIONS.get(cleaned, raw.strip())


def geocode_location(location_str: str) -> Optional[Tuple[float, float, str]]:
    """
    Returns (lat, lon, metro_area) or None.
    Uses Nominatim (free). Swap for Google if higher accuracy needed.
    """
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
    lat1: float, lon1: float,
    lat2: float, lon2: float,
    radius_miles: float = None,
) -> bool:
    radius = radius_miles or settings.location_cluster_radius_miles
    dist = geodesic((lat1, lon1), (lat2, lon2)).miles
    return dist <= radius


# ---------------------------------------------------------------------------
# Skill extraction
# ---------------------------------------------------------------------------

SKILL_ALIASES = {
    "python": "Python",
    "py": "Python",
    "sql": "SQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "r ": "R",
    "r,": "R",
    "tableau": "Tableau",
    "power bi": "Power BI",
    "powerbi": "Power BI",
    "excel": "Excel",
    "spark": "Apache Spark",
    "pyspark": "Apache Spark",
    "airflow": "Apache Airflow",
    "dbt": "dbt",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "google cloud": "GCP",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "pandas": "pandas",
    "numpy": "NumPy",
    "react": "React",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "java": "Java",
    "scala": "Scala",
    "go ": "Go",
    "golang": "Go",
    "rust": "Rust",
    "snowflake": "Snowflake",
    "databricks": "Databricks",
    "redshift": "Redshift",
    "bigquery": "BigQuery",
    "looker": "Looker",
    "sas": "SAS",
    "spss": "SPSS",
    "mlflow": "MLflow",
    "git": "Git",
    "linux": "Linux",
    "bash": "Bash",
    "shell": "Bash",
}

SKILL_CATEGORIES = {
    "Python": "Language",
    "SQL": "Language",
    "R": "Language",
    "Java": "Language",
    "Scala": "Language",
    "Go": "Language",
    "Rust": "Language",
    "JavaScript": "Language",
    "TypeScript": "Language",
    "Tableau": "Visualization",
    "Power BI": "Visualization",
    "Looker": "Visualization",
    "Excel": "Productivity",
    "AWS": "Cloud",
    "Azure": "Cloud",
    "GCP": "Cloud",
    "Docker": "DevOps",
    "Kubernetes": "DevOps",
    "PostgreSQL": "Database",
    "MySQL": "Database",
    "Snowflake": "Database",
    "BigQuery": "Database",
    "Redshift": "Database",
    "Databricks": "Data Platform",
    "Apache Spark": "Data Platform",
    "Apache Airflow": "Data Platform",
    "dbt": "Data Platform",
    "PyTorch": "ML",
    "TensorFlow": "ML",
    "scikit-learn": "ML",
    "MLflow": "ML",
    "pandas": "Library",
    "NumPy": "Library",
    "FastAPI": "Framework",
    "Django": "Framework",
    "Flask": "Framework",
    "React": "Framework",
    "SAS": "Analytics",
    "SPSS": "Analytics",
    "Git": "Tools",
    "Linux": "Tools",
    "Bash": "Tools",
}


def extract_skills(description: str) -> list[dict]:
    """Extract and normalize skills from job description text."""
    if not description:
        return []

    desc_lower = description.lower()
    found = {}

    for alias, normalized in SKILL_ALIASES.items():
        if alias in desc_lower and normalized not in found:
            found[normalized] = {
                "skill": normalized,
                "skill_normalized": normalized.lower(),
                "skill_category": SKILL_CATEGORIES.get(normalized),
            }

    return list(found.values())


# ---------------------------------------------------------------------------
# Job identity key
# ---------------------------------------------------------------------------

def build_job_identity_key(
    company_name: str,
    title_normalized: str,
    metro_area: Optional[str],
) -> str:
    """
    Canonical key: {company}_{title}_{metro}
    Used to detect reposts of the same role across time.
    """
    def slug(s: str) -> str:
        s = s.lower().strip()
        s = unicodedata.normalize("NFKD", s)
        s = re.sub(r"[^\w\s]", "", s)
        s = re.sub(r"\s+", "_", s)
        return s

    parts = [slug(company_name), slug(title_normalized)]
    if metro_area:
        parts.append(slug(metro_area.split(",")[0]))  # city only
    return "__".join(parts)
