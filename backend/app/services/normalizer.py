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
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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




def normalize_source_key(value: Any) -> str:
    """Normalize a publisher/source label into a stable database key."""
    key = _slug(value)
    return (key or "unknown")[:100]


_TRACKING_QUERY_KEYS = {
    "utm_campaign", "utm_source", "utm_medium", "utm_term", "utm_content",
    "gclid", "fbclid", "msclkid", "trk", "trackingid", "ref", "refid",
    "from", "src", "source", "campaign", "gh_src", "lever-source", "iis", "iisn",
}


def normalize_source_url(value: Any) -> Optional[str]:
    """Return a stable apply URL while removing common tracking parameters."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parts = urlsplit(text)
        if not parts.scheme or not parts.netloc:
            return text[:1000]
        query = [
            (key, item) for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in _TRACKING_QUERY_KEYS
        ]
        normalized = urlunsplit((
            parts.scheme.lower(),
            parts.netloc.lower().removeprefix("www."),
            parts.path.rstrip("/") or "/",
            urlencode(sorted(query)),
            "",
        ))
        return normalized[:1000]
    except ValueError:
        return text[:1000]


def build_source_sighting_key(source: Any, source_url: Any, external_id: Any = None) -> str:
    stable = "|".join((
        normalize_source_key(source),
        normalize_source_url(source_url) or "",
        str(external_id or "").strip(),
    ))
    return hashlib.sha256(stable.encode()).hexdigest()


def normalize_source_options(
    options: Any,
    *,
    primary_source: str,
    publisher_name: Optional[str],
    collection_provider: str,
    source_url: Optional[str],
    external_id: Any,
    applicant_count: Any,
) -> list[dict[str, Any]]:
    """Return one normalized sighting per distinct publisher/apply URL."""
    raw_options = options if isinstance(options, list) else []
    raw_options = [
        {
            "source": primary_source,
            "publisher_name": publisher_name,
            "collection_provider": collection_provider,
            "source_url": source_url,
            "external_id": external_id,
            "applicant_count": applicant_count,
        },
        *[item for item in raw_options if isinstance(item, dict)],
    ]

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_options:
        source = normalize_source_key(item.get("source") or item.get("publisher_name"))
        provider = normalize_source_key(
            item.get("collection_provider") or collection_provider or source
        )[:50]
        label = str(item.get("publisher_name") or source.replace("-", " ").title()).strip()[:255]
        item_external_id = item.get("external_id")
        normalized_url = normalize_source_url(item.get("source_url"))
        sighting_key = str(item.get("sighting_key") or build_source_sighting_key(
            source, normalized_url, item_external_id
        ))[:64]
        if sighting_key in seen:
            continue
        seen.add(sighting_key)
        result.append({
            "sighting_key": sighting_key,
            "source": source,
            "publisher_name": label,
            "collection_provider": provider,
            "source_url": normalized_url,
            "external_id": str(item_external_id)[:255] if item_external_id not in (None, "") else None,
            "applicant_count": item.get("applicant_count"),
            "is_direct": bool(item.get("is_direct", False)),
        })
    return result


def normalize_company_name(value: Any) -> str:
    text = _clean_words(value)
    text = re.sub(r"\b(incorporated|inc|llc|ltd|limited|corp|corporation|company|co)\b\.?", "", text)
    # Company.name_normalized is VARCHAR(255); keep every lookup and identity
    # calculation on the same bounded representation.
    return re.sub(r"\s+", " ", text).strip()[:255]


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
    # Keep role-defining families ahead of broader software/data patterns.
    ("forward deployed engineer", (
        r"\bforward[ -]?deployed(?: software)? engineer\b",
    )),
    ("machine learning engineer", (
        r"\b(machine learning|ml|ai) (engineer|developer)\b",
        r"\bmlops engineer\b",
    )),
    ("quantitative researcher", (
        r"\bquant(?:itative)? researcher\b",
        r"\bquant(?:itative)? research (?:analyst|engineer|scientist)\b",
        r"\bquant research(?:er| analyst| engineer| scientist)?\b",
    )),
    ("quantitative developer", (
        r"\bquant(?:itative)? developer\b",
        r"\bquant(?:itative)? strategy developer\b",
    )),
    ("quantitative trader", (
        r"\bquant(?:itative)? (?:systematic )?(?:trader|trading)\b",
        r"\bquant(?:itative)? trading analyst\b",
        r"\balgorithmic trader\b",
        r"\bsystematic (?:trader|trading)\b",
    )),
    ("quantitative analyst", (
        r"\bquant(?:itative)? (?:finance )?analyst\b",
        r"\bquantitative finance analyst\b",
        r"\bquantitative strategist\b",
    )),
    ("data scientist", (
        r"\bdata scientist\b",
        r"\bapplied scientist\b",
        r"\bresearch scientist\b",
    )),
    ("data engineer", (
        r"\bdata engineer\b",
        r"\banalytics engineer\b",
        r"\betl developer\b",
    )),
    ("data analyst", (
        r"\bdata analyst\b",
        r"\banalytics analyst\b",
        r"\bbi analyst\b",
        r"\bbusiness intelligence analyst\b",
    )),
    ("business systems analyst", (
        r"\bbusiness systems? analyst\b",
    )),
    ("business analyst", (
        r"\bbusiness analyst\b",
        r"\bsystems analyst\b",
    )),
    ("site reliability engineer", (
        r"\bsite reliability engineer\b",
        r"\bsre\b",
    )),
    ("devops engineer", (
        r"\bdevops\b",
        r"\bbuild and release engineer\b",
        r"\brelease engineer\b",
    )),
    ("security engineer", (
        r"\b(cyber ?security|information security|application security|security) (engineer|analyst)\b",
    )),
    ("cloud engineer", (r"\bcloud (engineer|developer)\b",)),
    ("solutions architect", (r"\b(solution|solutions|enterprise) architect\b",)),
    ("data architect", (r"\bdata architect\b",)),
    ("web developer", (
        r"\bweb (developer|engineer)\b",
    )),
    ("software engineer", (
        r"\bsoftware (engineer|developer)\b",
        r"\b(swe|sde)\b",
        r"\b(back[ -]?end|front[ -]?end|full[ -]?stack|platform|infrastructure) (engineer|developer)\b",
        r"\bapplication developer\b",
    )),
    ("qa engineer", (
        r"\b(qa|quality assurance|test automation|software test) (engineer|analyst)\b",
        r"\bsdet\b",
    )),
    ("product manager", (r"\bproduct manager\b", r"\btechnical product manager\b")),
    ("technical program manager", (r"\btechnical program manager\b", r"\btpm\b")),
    ("program manager", (r"\bprogram manager\b",)),
    ("project manager", (r"\bproject manager\b",)),
    ("product designer", (r"\b(product|ux|ui/ux) designer\b",)),
    ("systems administrator", (r"\b(system|systems) administrator\b", r"\bsysadmin\b")),
    ("database administrator", (r"\bdatabase administrator\b", r"\bdba\b")),
    ("network engineer", (r"\bnetwork engineer\b",)),
]

SPECIALTY_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    # Leadership and operating focus
    ("tech_lead", (r"(?:-|\(|,)\s*lead\b", r"\btech(?:nical)? lead\b")),
    ("admin", (r"\badmin(?:istration|istrator)?\b",)),

    # Application layer and architecture
    ("forward_deployed", (r"\bforward[ -]?deployed\b",)),
    ("backend", (r"\bback[ -]?end\b", r"\bserver[ -]?side\b")),
    ("frontend", (r"\bfront[ -]?end\b", r"\bclient[ -]?side\b", r"\breact(?:\.js)?\b")),
    ("fullstack", (r"\bfull[ -]?stack\b",)),
    ("web", (r"\bweb\b",)),
    ("api", (r"\bapi(?:s)?\b", r"\bgraphql\b", r"\brest(?:ful)?\b")),
    ("platform", (r"\bplatform\b",)),
    ("infrastructure", (r"\binfrastructure\b", r"\binfra\b")),
    ("distributed_systems", (r"\bdistributed systems?\b",)),
    ("microservices", (r"\bmicro[ -]?services?\b",)),

    # Cloud, reliability, and delivery
    ("cloud", (r"\bcloud\b", r"\baws\b", r"\bazure\b", r"\bgcp\b", r"\bgoogle cloud\b")),
    ("devops", (r"\bdevops\b", r"\bci[ /-]?cd\b", r"\bkubernetes\b", r"\bk8s\b")),
    ("site_reliability", (r"\bsite reliability\b", r"\bsre\b")),

    # Mobile and client platforms
    ("mobile", (r"\bmobile\b",)),
    ("ios", (r"\bios\b", r"\biphone\b", r"\bipad\b")),
    ("android", (r"\bandroid\b",)),

    # AI, machine learning, and data
    ("ml", (r"\bmachine learning\b", r"\bml\b", r"\bartificial intelligence\b", r"\bai\b")),
    ("mlops", (r"\bmlops\b", r"\bmachine learning platform\b")),
    ("generative_ai", (r"\bgenerative ai\b", r"\bgen[ -]?ai\b", r"\bllm(?:s)?\b", r"\blarge language models?\b")),
    ("nlp", (r"\bnlp\b", r"\bnatural language processing\b")),
    ("computer_vision", (r"\bcomputer vision\b", r"\bvision\b")),
    ("data", (r"\bdata\b", r"\betl\b", r"\belt\b")),
    ("data_platform", (r"\bdata platform\b", r"\bdata infrastructure\b")),
    ("analytics", (r"\banalytics\b", r"\bbusiness intelligence\b", r"\bbi\b")),
    ("business_systems", (r"\bbusiness systems?\b",)),
    ("quant_research", (
        r"\bquant(?:itative)? research(?:er| analyst| engineer| scientist)?\b",
        r"\bquant(?:itative)? researcher\b",
    )),
    ("quant_development", (
        r"\bquant(?:itative)? developer\b",
        r"\bquant(?:itative)? strategy developer\b",
    )),
    ("quant_trading", (
        r"\bquant(?:itative)? (?:systematic )?(?:trader|trading)\b",
        r"\bquant(?:itative)? trading analyst\b",
        r"\balgorithmic trader\b",
    )),
    ("database", (r"\bdatabase\b", r"\bdb\b", r"\bsql\b")),

    # Security and quality
    ("security", (r"\bsecurity\b", r"\bcyber(?:security)?\b")),
    ("application_security", (r"\bapplication security\b", r"\bappsec\b")),
    ("cloud_security", (r"\bcloud security\b",)),
    ("identity_access", (r"\bidentity and access\b", r"\bidentity access\b", r"\biam\b")),
    ("detection_response", (r"\bdetection and response\b", r"\bincident response\b", r"\bsoc\b")),
    ("quality", (r"\bqa\b", r"\bquality assurance\b", r"\bsoftware test\b")),
    ("test_automation", (r"\btest automation\b", r"\bautomation test\b", r"\bsdet\b")),
    ("security_clearance", (
        r"\btop secret\b",
        r"\bts[\s/-]*sci\b",
        r"\bsecret clearance\b",
        r"\bsecurity clearance\b",
        r"\bclearance required\b",
        r"\bclearance eligib(?:le|ility)\b",
        r"\b(?:dod|department of defense|government) clearance\b",
        r"\bpublic trust\b",
        r"\bpolygraph\b",
    )),

    # Systems, hardware, networking, and specialized engineering
    ("embedded", (r"\bembedded\b",)),
    ("firmware", (r"\bfirmware\b",)),
    ("robotics", (r"\brobotics?\b", r"\bautonomous systems?\b")),
    ("hardware", (r"\bhardware\b", r"\bfpga\b", r"\basic\b")),
    ("network", (r"\bnetwork(?:ing)?\b",)),
    ("telecom", (r"\btelecom(?:munications)?\b", r"\b5g\b")),
    ("geospatial", (r"\bgeospatial\b", r"\bgis\b", r"\bmapping\b")),

    # Enterprise application ecosystems. These are identity-defining because
    # jobs on different enterprise platforms are usually different requisitions.
    ("windchill", (r"\bwindchill\b", r"\bptc windchill\b", r"\bplm\b")),
    ("salesforce", (r"\bsalesforce\b", r"\bapex\b")),
    ("sap", (r"\bsap\b", r"\babap\b")),
    ("servicenow", (r"\bservice[ -]?now\b",)),
    ("workday", (r"\bworkday\b",)),
    ("oracle", (r"\boracle\b", r"\bpeoplesoft\b")),

    # Programming languages. Canonical tags combine common aliases so
    # "Go Engineer" and "Golang Engineer" retain the same specialization.
    ("golang", (
        r"\bgolang\b",
        r"\bgo language\b",
        r"\bgo(?:lang)?\b(?=\s+(?:software\s+)?(?:engineer|developer)\b)",
        r"\b(?:engineer|developer)[, /-]+go(?:lang)?\b",
    )),
    ("python", (r"\bpython\b",)),
    ("java", (r"\bjava\b",)),
    ("javascript", (r"\bjavascript\b", r"\bnode(?:\.js)?\b", r"\breact(?:\.js)?\b")),
    ("typescript", (r"\btypescript\b",)),
    ("csharp", (r"\bc#\b", r"\bc sharp\b", r"\b\.net\b", r"\bdotnet\b")),
    ("cpp", (r"\bc\+\+\b", r"\bc plus plus\b")),
    ("rust", (r"\brust\b",)),
    ("ruby", (r"\bruby\b", r"\brails\b")),
    ("php", (r"\bphp\b",)),
    ("scala", (r"\bscala\b",)),
    ("kotlin", (r"\bkotlin\b",)),
    ("swift", (r"\bswift\b",)),

    # Product and industry domains that help distinguish otherwise generic
    # software-engineering titles at the same employer.
    ("payments", (r"\bpayments?\b", r"\bbilling\b")),
    ("fraud", (r"\bfraud\b", r"\brisk platform\b")),
    ("growth", (r"\bgrowth\b",)),
    ("fintech", (r"\bfintech\b", r"\bfinancial technology\b")),
    ("healthcare", (r"\bhealthcare\b", r"\bhealth tech\b", r"\bclinical\b")),
    ("ecommerce", (r"\be[ -]?commerce\b", r"\bmarketplace\b")),
    ("adtech", (r"\bad[ -]?tech\b", r"\badvertising\b")),
    ("gaming", (r"\bgaming\b", r"\bgameplay\b", r"\bgame engine\b")),
    ("blockchain", (r"\bblockchain\b", r"\bweb3\b", r"\bcrypto\b")),
]


# These tags materially narrow the role. If one title has one of these tags
# and the other title is completely generic, JobLens should not group the two
# unless strong description evidence confirms they are the same requisition.
IDENTITY_DEFINING_SPECIALIZATIONS: frozenset[str] = frozenset({
    "backend", "frontend", "fullstack", "api", "platform", "infrastructure",
    "distributed_systems", "microservices", "cloud", "devops", "site_reliability",
    "mobile", "ios", "android", "ml", "mlops", "generative_ai", "nlp",
    "computer_vision", "data", "data_platform", "analytics", "database",
    "security", "application_security", "cloud_security", "identity_access",
    "detection_response", "quality", "test_automation", "embedded", "firmware",
    "robotics", "hardware", "network", "telecom", "geospatial", "windchill",
    "salesforce", "sap", "servicenow", "workday", "oracle", "golang", "python",
    "java", "javascript", "typescript", "csharp", "cpp", "rust", "ruby", "php",
    "scala", "kotlin", "swift", "payments", "fraud", "growth", "fintech",
    "healthcare", "ecommerce", "adtech", "gaming", "blockchain",
    "forward_deployed", "web", "business_systems", "quant_research",
    "quant_development", "quant_trading", "security_clearance",
})


PRIMARY_IDENTITY_SPECIALIZATIONS: frozenset[str] = frozenset({
    # Languages
    "golang", "python", "java", "javascript", "typescript", "csharp", "cpp",
    "rust", "ruby", "php", "scala", "kotlin", "swift",
    # Enterprise platforms
    "windchill", "salesforce", "sap", "servicenow", "workday", "oracle",
    # AI, data, security, mobile, systems, and industry subdomains
    "ml", "mlops", "generative_ai", "nlp", "computer_vision", "data",
    "data_platform", "analytics", "database", "application_security",
    "cloud_security", "identity_access", "detection_response", "ios", "android",
    "embedded", "firmware", "robotics", "hardware", "network", "telecom",
    "geospatial", "payments", "fraud", "growth", "fintech", "healthcare",
    "ecommerce", "adtech", "gaming", "blockchain",
    "forward_deployed", "web", "business_systems", "quant_research",
    "quant_development", "quant_trading",
    # A materially different clearance requirement can indicate a distinct
    # opening even when every other title signal matches.
    "security_clearance",
})


# Tags within one dimension cannot identify the same role when both sides name
# different values. For example, an iOS role is not the same as an Android role,
# and a Windchill role is not the same as a Salesforce role.
EXCLUSIVE_SPECIALIZATION_DIMENSIONS: tuple[frozenset[str], ...] = (
    frozenset({"backend", "frontend"}),
    frozenset({"ios", "android"}),
    frozenset({"windchill", "salesforce", "sap", "servicenow", "workday", "oracle"}),
    frozenset({"golang", "python", "java", "javascript", "typescript", "csharp", "cpp", "rust", "ruby", "php", "scala", "kotlin", "swift"}),
    frozenset({"quant_research", "quant_development", "quant_trading"}),
)


def extract_specializations(raw_title: Any) -> list[str]:
    """Return stable specialization tags extracted from a job title."""
    cleaned = _clean_words(raw_title)
    tags = [
        name for name, patterns in SPECIALTY_PATTERNS
        if any(re.search(pattern, cleaned, flags=re.I) for pattern in patterns)
    ]
    return sorted(dict.fromkeys(tags))


def specialization_sets_conflict(first: set[str], second: set[str]) -> bool:
    """Return True when two non-empty specialization sets identify different roles."""
    if not first or not second:
        return False

    # Detect conflicts in exclusive dimensions even when the two titles also
    # share a broad tag such as "backend" or "platform". For example,
    # "Java Backend Engineer" and "Python Backend Engineer" remain different.
    for dimension in EXCLUSIVE_SPECIALIZATION_DIMENSIONS:
        left = first.intersection(dimension)
        right = second.intersection(dimension)
        if left and right and left.isdisjoint(right):
            return True

    primary_left = first.intersection(PRIMARY_IDENTITY_SPECIALIZATIONS)
    primary_right = second.intersection(PRIMARY_IDENTITY_SPECIALIZATIONS)
    if bool(primary_left) != bool(primary_right):
        return True
    if primary_left and primary_right and primary_left.isdisjoint(primary_right):
        return True

    if first.intersection(second):
        return False

    # For canonical identity, two disjoint identity-defining specializations
    # are treated conservatively as different roles. This prevents broad family
    # labels such as "software engineer" from collapsing unrelated requisitions.
    return bool(
        first.intersection(IDENTITY_DEFINING_SPECIALIZATIONS)
        and second.intersection(IDENTITY_DEFINING_SPECIALIZATIONS)
    )



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

    specialties = extract_specializations(cleaned)
    if family in {"systems administrator", "database administrator"}:
        # The "admin" specialty pattern matches the literal word
        # "administrator", which is also what the family match itself keyed
        # on. For these two families it restates the family rather than
        # adding a differentiating signal (unlike "Software Engineer -
        # Admin", where family is unrelated and "admin" is genuinely
        # informative) — e.g. "IT Systems Administrator (Aerospace)" and
        # "IT Systems Administrator (Server)" would otherwise both collapse
        # to specialization="admin" and be treated as a confirmed shared
        # specialization signal despite naming different roles.
        specialties = [tag for tag in specialties if tag != "admin"]

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


def normalize_metro_area(value: Any) -> Optional[str]:
    """Return a database-safe analysis bucket while preserving raw locations separately."""
    normalized = normalize_location_text(value)
    if not normalized:
        return None
    if "|" in normalized or ";" in normalized:
        return "Multiple locations"
    return normalized[:500]


def infer_location_components(location_raw: Any) -> dict[str, Optional[str]]:
    normalized = normalize_location_text(location_raw)
    if not normalized:
        return {"city": None, "state": None, "country": "US", "metro_area": None}
    if REMOTE_RE.search(normalized):
        return {"city": None, "state": None, "country": "US", "metro_area": "Remote"}
    # Preserve the full list in location_raw; use a stable short bucket for analysis.
    if "|" in normalized or ";" in normalized:
        return {"city": None, "state": None, "country": "US", "metro_area": "Multiple locations"}
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
    title_raw = str(record.get("title_raw") or record.get("title") or "").strip()[:500]
    company_name = str(record.get("company_name") or record.get("company") or "").strip()[:255]
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
    metro_area = normalize_metro_area(record.get("metro_area") or components["metro_area"])

    salary_min, salary_max = annualize_salary(
        record.get("salary_min"), record.get("salary_max"), record.get("salary_period", "year")
    )
    description = record.get("description_raw") or ""

    source = normalize_source_key(record.get("source"))
    collection_provider = normalize_source_key(record.get("collection_provider") or source)[:50]
    publisher_name = str(
        record.get("publisher_name") or source.replace("-", " ").title()
    ).strip()[:255]
    source_url = normalize_source_url(record.get("source_url"))
    external_id = record.get("external_id")
    source_options = normalize_source_options(
        record.get("source_options"),
        primary_source=source,
        publisher_name=publisher_name,
        collection_provider=collection_provider,
        source_url=source_url,
        external_id=external_id,
        applicant_count=record.get("applicant_count"),
    )

    record.update({
        "source": source,
        "publisher_name": publisher_name,
        "collection_provider": collection_provider,
        "source_options": source_options,
        "source_url": source_url,
        "external_id": str(external_id)[:255] if external_id not in (None, "") else None,
        "company_name": company_name,
        "title_raw": title_raw,
        "title_normalized": str(parts["title_normalized"] or "")[:500],
        "job_family": str(family or "")[:500] or None,
        "specialization": str(specialization or "")[:300] or None,
        "title_parse_confidence": parts["confidence"],
        "seniority": str(seniority or "")[:50] or None,
        "employment_type": str(employment_type or "")[:50] or None,
        "location_raw": location_raw,
        "city": str(record.get("city") or components["city"] or "")[:200] or None,
        "state": str(record.get("state") or components["state"] or "")[:100] or None,
        "country": str(record.get("country") or components["country"] or "US")[:100],
        "metro_area": str(metro_area or "")[:500] or None,
        "remote_type": str(remote_type or "")[:50] or None,
        "latitude": record.get("latitude"),
        "longitude": record.get("longitude"),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": str(record.get("salary_currency") or "USD")[:10],
        "salary_listed": salary_min is not None or salary_max is not None,
        "description_raw": description,
        "date_posted": parse_datetime(record.get("date_posted")),
        "applicant_count": record.get("applicant_count"),
        "education_required": str(record.get("education_required") or "").strip()[:200] or None,
        "experience_years_min": record.get("experience_years_min"),
        "experience_years_max": record.get("experience_years_max"),
        "department": str(record.get("department") or "").strip()[:200] or None,
        "industry": str(record.get("industry") or "").strip()[:200] or None,
        "company_website": (normalize_source_url(record.get("company_website")) or "")[:500] or None,
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
