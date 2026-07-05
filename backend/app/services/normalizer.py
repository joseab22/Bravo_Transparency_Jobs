"""Pure normalization helpers used by every scraper and ingestion path.

No function in this module performs network I/O. Location geocoding and
embedding generation are deliberately separate enrichment tasks.
"""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from app.core.config import settings
from app.core.time import utc_now


def _ascii_text(value: Any) -> str:
    text = "" if value is None else str(value)
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def _clean_words(value: Any) -> str:
    text = _ascii_text(value).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9+#./-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip(" -/.")


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _clean_words(value)).strip("-")


def normalize_company_name(value: Any) -> str:
    text = _clean_words(value)
    text = re.sub(r"\b(incorporated|inc|llc|ltd|limited|corp|corporation|company|co)\b\.?", "", text)
    return re.sub(r"\s+", " ", text).strip()


SENIORITY_PATTERNS: list[tuple[str, str]] = [
    (r"\b(chief|c[etf]o|vice president|vp|head of|director)\b", "Executive"),
    # Explicit seniority wins over a trailing role modifier such as
    # "Senior Software Engineer - Lead"; "lead" remains a specialization.
    (r"\b(senior|sr\.?|level\s*[45]|[45])\b", "Senior"),
    (r"\b(principal|distinguished|fellow)\b", "Lead"),
    (r"\b(staff|lead|manager|architect)\b", "Lead"),
    (r"\b(junior|jr\.?|entry[ -]?level|new grad|graduate|associate|level\s*1|i)\b", "Entry"),
    (r"\b(intern|internship|co[ -]?op|apprentice)\b", "Entry"),
]

FAMILY_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("machine learning engineer", (r"\b(machine learning|ml|ai) (engineer|developer)\b", r"\bmlops engineer\b")),
    ("data scientist", (r"\bdata scientist\b", r"\bapplied scientist\b", r"\bresearch scientist\b")),
    ("data engineer", (r"\bdata engineer\b", r"\banalytics engineer\b", r"\betl developer\b")),
    ("data analyst", (r"\bdata analyst\b", r"\banalytics analyst\b", r"\bbi analyst\b", r"\bbusiness intelligence analyst\b")),
    ("business analyst", (r"\bbusiness analyst\b", r"\bsystems analyst\b")),
    ("site reliability engineer", (r"\bsite reliability engineer\b", r"\bsre\b")),
    ("devops engineer", (r"\bdevops\b", r"\bbuild and release engineer\b", r"\brelease engineer\b")),
    ("security engineer", (r"\b(cyber ?security|information security|application security|security) (engineer|analyst)\b",)),
    ("cloud engineer", (r"\bcloud (engineer|developer)\b",)),
    ("solutions architect", (r"\b(solution|solutions|enterprise) architect\b",)),
    ("data architect", (r"\bdata architect\b",)),
    ("software engineer", (
        r"\bsoftware (engineer|developer)\b", r"\b(swe|sde)\b",
        r"\b(back[ -]?end|front[ -]?end|full[ -]?stack|platform|infrastructure) (engineer|developer)\b",
        r"\bapplication developer\b", r"\bweb developer\b",
    )),
    ("qa engineer", (r"\b(qa|quality assurance|test automation|software test) (engineer|analyst)\b", r"\bsdet\b")),
    ("product manager", (r"\bproduct manager\b", r"\btechnical product manager\b")),
    ("technical program manager", (r"\btechnical program manager\b", r"\btpm\b")),
    ("program manager", (r"\bprogram manager\b",)),
    ("project manager", (r"\bproject manager\b",)),
    ("product designer", (r"\b(product|ux|ui/ux) designer\b",)),
    ("systems administrator", (r"\b(system|systems) administrator\b", r"\bsysadmin\b")),
    ("database administrator", (r"\bdatabase administrator\b", r"\bdba\b")),
    ("network engineer", (r"\bnetwork engineer\b",)),
    ("quantitative analyst", (r"\bquant(itative)? (analyst|researcher|developer)\b",)),
]

SPECIALTY_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("tech_lead", (r"(?:-|\(|,)\s*lead\b", r"\btech(nical)? lead\b")),
    ("admin", (r"\badmin(istration|istrator)?\b", r"\bsalesforce\b")),
    ("backend", (r"\bback[ -]?end\b", r"\bserver[ -]?side\b")),
    ("frontend", (r"\bfront[ -]?end\b", r"\bclient[ -]?side\b", r"\breact\b")),
    ("fullstack", (r"\bfull[ -]?stack\b",)),
    ("platform", (r"\bplatform\b",)),
    ("infrastructure", (r"\binfrastructure\b", r"\binfra\b")),
    ("cloud", (r"\bcloud\b", r"\baws\b", r"\bazure\b", r"\bgcp\b")),
    ("security", (r"\bsecurity\b", r"\bcyber\b")),
    ("devops", (r"\bdevops\b", r"\bci/cd\b", r"\bkubernetes\b")),
    ("mobile", (r"\bmobile\b",)),
    ("ios", (r"\bios\b", r"\bswift\b")),
    ("android", (r"\bandroid\b", r"\bkotlin\b")),
    ("ml", (r"\bmachine learning\b", r"\bml\b", r"\bartificial intelligence\b", r"\bai\b")),
    ("data", (r"\bdata\b", r"\betl\b")),
    ("analytics", (r"\banalytics\b", r"\bbusiness intelligence\b")),
    ("quality", (r"\bqa\b", r"\bquality\b", r"\btest automation\b")),
    ("embedded", (r"\bembedded\b",)),
    ("firmware", (r"\bfirmware\b",)),
    ("distributed_systems", (r"\bdistributed systems?\b",)),
    ("database", (r"\bdatabase\b", r"\bsql\b")),
    ("network", (r"\bnetwork(ing)?\b",)),
    ("payments", (r"\bpayments?\b",)),
    ("fraud", (r"\bfraud\b", r"\brisk\b")),
    ("growth", (r"\bgrowth\b",)),
]


def extract_seniority(title: Any) -> Optional[str]:
    text = _clean_words(title)
    for pattern, level in SENIORITY_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            return level
    return "Mid" if text else None


def decompose_title(raw_title: Any) -> dict[str, Any]:
    cleaned = _clean_words(raw_title)
    family: Optional[str] = None
    for canonical, patterns in FAMILY_PATTERNS:
        if any(re.search(pattern, cleaned, flags=re.I) for pattern in patterns):
            family = canonical
            break

    specialties = [
        name for name, patterns in SPECIALTY_PATTERNS
        if any(re.search(pattern, cleaned, flags=re.I) for pattern in patterns)
    ]
    specialties = sorted(dict.fromkeys(specialties))

    seniority = extract_seniority(cleaned)
    if family:
        confidence = 0.96 if cleaned == family else 0.90
        normalized = family
    else:
        # Keep the unknown title informative rather than forcing a bad family.
        stripped = cleaned
        for pattern, _ in SENIORITY_PATTERNS:
            stripped = re.sub(pattern, " ", stripped, flags=re.I)
        normalized = re.sub(r"\s+", " ", stripped).strip(" -/.") or cleaned
        family = None
        confidence = 0.55 if normalized else 0.0

    return {
        "raw_title": str(raw_title or ""),
        "title_normalized": normalized,
        "core_title": family or normalized,
        "job_family": family,
        "specialization": ",".join(specialties) if specialties else None,
        "specializations": specialties,
        "seniority": seniority,
        "confidence": confidence,
    }


def normalize_title(raw_title: Any) -> str:
    return decompose_title(raw_title)["title_normalized"]


REMOTE_RE = re.compile(r"\b(remote|work from home|wfh|anywhere|distributed)\b", re.I)
HYBRID_RE = re.compile(r"\b(hybrid|flexible location)\b", re.I)


def normalize_remote_type(value: Any, location_raw: Any = None) -> str:
    text = f"{_clean_words(value)} {_clean_words(location_raw)}"
    if HYBRID_RE.search(text):
        return "Hybrid"
    if REMOTE_RE.search(text):
        return "Remote"
    return "Onsite"


def normalize_employment_type(value: Any, title: Any = None) -> str:
    text = f"{_clean_words(value)} {_clean_words(title)}"
    if re.search(r"\b(intern|internship|co op)\b", text):
        return "Internship"
    if re.search(r"\b(contract|contractor|temporary|temp)\b", text):
        return "Contract"
    if re.search(r"\bpart[ -]?time\b", text):
        return "Part-time"
    return "Full-time"


STATE_NAMES = {
    "alabama":"AL","alaska":"AK","arizona":"AZ","arkansas":"AR","california":"CA",
    "colorado":"CO","connecticut":"CT","delaware":"DE","florida":"FL","georgia":"GA",
    "hawaii":"HI","idaho":"ID","illinois":"IL","indiana":"IN","iowa":"IA",
    "kansas":"KS","kentucky":"KY","louisiana":"LA","maine":"ME","maryland":"MD",
    "massachusetts":"MA","michigan":"MI","minnesota":"MN","mississippi":"MS","missouri":"MO",
    "montana":"MT","nebraska":"NE","nevada":"NV","new hampshire":"NH","new jersey":"NJ",
    "new mexico":"NM","new york":"NY","north carolina":"NC","north dakota":"ND","ohio":"OH",
    "oklahoma":"OK","oregon":"OR","pennsylvania":"PA","rhode island":"RI","south carolina":"SC",
    "south dakota":"SD","tennessee":"TN","texas":"TX","utah":"UT","vermont":"VT",
    "virginia":"VA","washington":"WA","west virginia":"WV","wisconsin":"WI","wyoming":"WY",
    "district of columbia":"DC",
}


def normalize_location_text(value: Any) -> Optional[str]:
    if not value:
        return None
    text = _ascii_text(value).strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    for name, abbr in STATE_NAMES.items():
        text = re.sub(rf"\b{re.escape(name)}\b", abbr, text, flags=re.I)
    return text[:500]


def infer_location_components(location_raw: Any) -> dict[str, Optional[str]]:
    normalized = normalize_location_text(location_raw)
    if not normalized:
        return {"city": None, "state": None, "country": "US", "metro_area": None}
    if REMOTE_RE.search(normalized):
        return {"city": None, "state": None, "country": "US", "metro_area": "Remote"}
    # Multi-location strings should remain one normalized label until enrichment.
    if "|" in normalized or ";" in normalized:
        return {"city": None, "state": None, "country": "US", "metro_area": normalized}
    parts = [part.strip() for part in normalized.split(",") if part.strip()]
    city = parts[0] if parts else None
    state = None
    for part in parts[1:]:
        candidate = part.upper()
        if re.fullmatch(r"[A-Z]{2}", candidate):
            state = candidate
            break
    metro = ", ".join([p for p in (city, state) if p]) or normalized
    return {"city": city, "state": state, "country": "US", "metro_area": metro}


def location_bucket(location_raw: Any, remote_type: Any, metro_area: Any = None) -> str:
    work = normalize_remote_type(remote_type, location_raw)
    if work == "Remote":
        return "remote"
    return _slug(metro_area or location_raw or "unknown")


def locations_in_same_cluster(
    latitude_a: Optional[float], longitude_a: Optional[float],
    latitude_b: Optional[float], longitude_b: Optional[float],
    radius_miles: Optional[float] = None,
) -> bool:
    if None in (latitude_a, longitude_a, latitude_b, longitude_b):
        return False
    radius = radius_miles or settings.location_cluster_radius_miles
    lat1, lon1, lat2, lon2 = map(math.radians, (latitude_a, longitude_a, latitude_b, longitude_b))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h)) <= radius


SKILL_PATTERNS: dict[str, tuple[str, ...]] = {
    "Python": (r"\bpython\b",), "SQL": (r"\bsql\b",), "Java": (r"\bjava\b",),
    "JavaScript": (r"\bjavascript\b", r"\bjs\b"), "TypeScript": (r"\btypescript\b",),
    "React": (r"\breact(?:\.js)?\b",), "Node.js": (r"\bnode(?:\.js)?\b",),
    "AWS": (r"\baws\b", r"amazon web services"), "Azure": (r"\bazure\b",), "GCP": (r"\bgcp\b", r"google cloud"),
    "Docker": (r"\bdocker\b",), "Kubernetes": (r"\bkubernetes\b", r"\bk8s\b"),
    "Spark": (r"\bapache spark\b", r"\bspark\b"), "PyTorch": (r"\bpytorch\b",),
    "TensorFlow": (r"\btensorflow\b",), "Tableau": (r"\btableau\b",), "Power BI": (r"\bpower bi\b",),
    "Excel": (r"\bexcel\b",), "Git": (r"\bgit\b",), "Linux": (r"\blinux\b",),
}


def extract_skills(text: Any) -> list[dict[str, Optional[str]]]:
    value = _ascii_text(text).lower()
    result = []
    for canonical, patterns in SKILL_PATTERNS.items():
        if any(re.search(pattern, value, flags=re.I) for pattern in patterns):
            result.append({"skill": canonical, "skill_normalized": canonical.lower(), "skill_category": None})
    return result


def annualize_salary(minimum: Any, maximum: Any, period: Any = "year") -> tuple[Optional[int], Optional[int]]:
    def numeric(value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            return float(re.sub(r"[^0-9.]", "", str(value)))
        except (TypeError, ValueError):
            return None
    low, high = numeric(minimum), numeric(maximum)
    multiplier = {
        "hour": 2080, "hourly": 2080, "day": 260, "daily": 260,
        "week": 52, "weekly": 52, "month": 12, "monthly": 12,
        "year": 1, "yearly": 1, "annual": 1,
    }.get(_clean_words(period), 1)
    return (
        round(low * multiplier) if low is not None else None,
        round(high * multiplier) if high is not None else None,
    )


def build_identity_fingerprint(
    company_name: Any,
    job_family: Any,
    specialization: Any = None,
    seniority: Any = None,
    employment_type: Any = None,
    remote_type: Any = None,
) -> str:
    components = [
        normalize_company_name(company_name), _slug(job_family), _slug(specialization),
        _slug(seniority), _slug(employment_type), _slug(remote_type),
    ]
    return hashlib.sha256("|".join(components).encode()).hexdigest()


def build_job_identity_key(
    company_name: Any,
    title_or_family: Any,
    metro_area: Any = None,
    *, specialization: Any = None,
    seniority: Any = None,
    employment_type: Any = None,
    remote_type: Any = None,
) -> str:
    fingerprint = build_identity_fingerprint(
        company_name, title_or_family, specialization, seniority, employment_type, remote_type
    )[:20]
    bucket = location_bucket(metro_area, remote_type, metro_area)
    return f"{normalize_company_name(company_name)}|{_slug(title_or_family)}|{bucket}|{fingerprint}"[:500]


def parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)) and value > 0:
        timestamp = float(value)
        if timestamp > 10_000_000_000:  # milliseconds
            timestamp /= 1000
        try:
            dt = datetime.utcfromtimestamp(timestamp)
        except (OverflowError, OSError, ValueError):
            return None
    elif value:
        text = str(value).strip()
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
                try:
                    dt = datetime.strptime(text[:10], fmt)
                    break
                except ValueError:
                    dt = None
            if dt is None:
                return None
    else:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def calculate_days_active(
    date_posted: Optional[datetime], date_first_seen: Optional[datetime], now: Optional[datetime] = None
) -> int:
    now = now or utc_now()
    candidates = [dt for dt in (parse_datetime(date_posted), parse_datetime(date_first_seen)) if dt and dt <= now]
    start = min(candidates) if candidates else now
    return max((now - start).days, 0)


def prepare_job_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Central normalization contract for every source before persistence."""
    record = dict(raw)
    title_raw = str(record.get("title_raw") or record.get("title") or "").strip()
    company_name = str(record.get("company_name") or record.get("company") or "").strip()
    if not title_raw or not company_name:
        raise ValueError("A job requires title_raw and company_name")

    parts = decompose_title(title_raw)
    location_raw = normalize_location_text(record.get("location_raw"))
    components = infer_location_components(location_raw)
    remote_type = normalize_remote_type(record.get("remote_type"), location_raw)
    employment_type = normalize_employment_type(record.get("employment_type"), title_raw)
    seniority = record.get("seniority") or parts["seniority"]
    family = parts["job_family"] or parts["title_normalized"]
    specialization = record.get("specialization") or parts["specialization"]
    metro_area = record.get("metro_area") or components["metro_area"]

    salary_min, salary_max = annualize_salary(
        record.get("salary_min"), record.get("salary_max"), record.get("salary_period", "year")
    )
    description = record.get("description_raw") or ""

    record.update({
        "source": str(record.get("source") or "").lower(),
        "company_name": company_name,
        "title_raw": title_raw,
        "title_normalized": parts["title_normalized"],
        "job_family": family,
        "specialization": specialization,
        "title_parse_confidence": parts["confidence"],
        "seniority": seniority,
        "employment_type": employment_type,
        "location_raw": location_raw,
        "city": record.get("city") or components["city"],
        "state": record.get("state") or components["state"],
        "country": record.get("country") or components["country"] or "US",
        "metro_area": metro_area,
        "remote_type": remote_type,
        "latitude": record.get("latitude"),
        "longitude": record.get("longitude"),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": record.get("salary_currency") or "USD",
        "salary_listed": salary_min is not None or salary_max is not None,
        "description_raw": description,
        "date_posted": parse_datetime(record.get("date_posted")),
        "applicant_count": record.get("applicant_count"),
        "skills": record.get("skills") or extract_skills(description),
    })
    record["identity_fingerprint"] = build_identity_fingerprint(
        company_name, family, specialization, seniority, employment_type, remote_type
    )
    record["job_identity_key"] = build_job_identity_key(
        company_name, family, metro_area,
        specialization=specialization, seniority=seniority,
        employment_type=employment_type, remote_type=remote_type,
    )
    return record


def embed_text(text: str) -> list[float]:
    """Lazy embedding helper retained for explicit enrichment tasks."""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(settings.embedding_model)
    return model.encode(text, normalize_embeddings=True).tolist()
